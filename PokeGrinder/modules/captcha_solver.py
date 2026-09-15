import requests
import cv2
import numpy as np
from PIL import Image
from io import BytesIO
from pathlib import Path
import json
from ultralytics import YOLO

BASE_DIR = Path(__file__).resolve().parents[1]
model = YOLO(str(BASE_DIR / "assets" / "Solver100k.pt"))
TUNING_PATH = BASE_DIR / "assets" / "captcha_samples" / "solver_tuning.json"

DEFAULT_TUNING: dict[str, object] = {
    "conf_threshold": 0.5,
    "merge_distance": 8.0,
    "min_length": 3,
    "max_length": 6,
    "plausible_length_bonus": 0.02,
    "variant_weights": {
        "raw": 1.0,
        "th120": 1.0,
        "th120_med": 1.0,
        "th135_open2": 1.0,
    },
    "close_score_delta": 0.02,
    "preferred_variant_order": ["th120_med", "th135_open2", "raw", "th120"],
}


def _load_tuning() -> dict[str, object]:
    tuning = dict(DEFAULT_TUNING)
    try:
        if TUNING_PATH.exists():
            data = json.loads(TUNING_PATH.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                tuning.update(data)
    except Exception:
        # Keep runtime robust even if tuning file is malformed.
        pass
    return tuning


def _prepare_variants(image: Image.Image) -> dict[str, Image.Image]:
    gray = np.array(image.convert("L"), dtype=np.uint8)

    variants: dict[str, np.ndarray] = {"raw": gray}

    _, th120 = cv2.threshold(gray, 120, 255, cv2.THRESH_BINARY)
    variants["th120"] = th120
    variants["th120_med"] = cv2.medianBlur(th120, 3)

    _, th135 = cv2.threshold(gray, 135, 255, cv2.THRESH_BINARY)
    kernel2 = np.ones((2, 2), np.uint8)
    variants["th135_open2"] = cv2.morphologyEx(th135, cv2.MORPH_OPEN, kernel2)

    return {name: Image.fromarray(arr) for name, arr in variants.items()}


def _char_for_class(class_id: int, names: dict | list | None) -> str:
    if isinstance(names, dict):
        return str(names.get(class_id, class_id))
    if isinstance(names, list) and 0 <= class_id < len(names):
        return str(names[class_id])
    return str(class_id)


def _decode_with_postprocess(
    image: Image.Image,
    conf_threshold: float = 0.5,
    merge_distance: float = 8.0,
) -> tuple[str, float, list[tuple[float, str, float]]]:
    result = model.predict(
        image,
        imgsz=320,
        save=False,
        agnostic_nms=True,
        max_det=12,
        verbose=False,
    )[0]

    boxes = result.boxes
    if boxes is None or boxes.cls is None or len(boxes.cls) == 0:
        return "", 0.0, []

    classes = [int(v) for v in boxes.cls.tolist()]
    confidences = boxes.conf.tolist() if boxes.conf is not None else [1.0] * len(classes)
    xyxy = boxes.xyxy.tolist() if boxes.xyxy is not None else []

    detections: list[tuple[float, str, float]] = []
    for index, class_id in enumerate(classes):
        confidence = float(confidences[index])
        if confidence < conf_threshold:
            continue

        x_min = float(xyxy[index][0]) if index < len(xyxy) else float(index)
        label = _char_for_class(class_id, getattr(result, "names", None))
        detections.append((x_min, label, confidence))

    if not detections:
        return "", 0.0, []

    detections.sort(key=lambda item: item[0])

    groups: list[list[tuple[float, str, float]]] = []
    current_group: list[tuple[float, str, float]] = [detections[0]]
    for det in detections[1:]:
        if abs(det[0] - current_group[-1][0]) <= merge_distance:
            current_group.append(det)
        else:
            groups.append(current_group)
            current_group = [det]
    groups.append(current_group)

    picked = [max(group, key=lambda item: item[2]) for group in groups]
    text = "".join([entry[1] for entry in picked])
    score = sum(entry[2] for entry in picked)
    return text, score, picked


def _prune_noise_chars(picked: list[tuple[float, str, float]]) -> str:
    if len(picked) < 2:
        return "".join([entry[1] for entry in picked])

    chars = list(picked)

    def median_gap(entries: list[tuple[float, str, float]]) -> float:
        if len(entries) < 3:
            return 0.0
        xs = [entry[0] for entry in entries]
        gaps = [xs[index + 1] - xs[index] for index in range(len(xs) - 1)]
        if not gaps:
            return 0.0
        return float(np.median(gaps))

    changed = True
    while changed and len(chars) >= 3:
        changed = False
        med_gap = median_gap(chars)
        if med_gap <= 0:
            break

        # Rule 1: collapse tight repeated adjacent characters by dropping weaker one.
        index = 0
        while index < len(chars) - 1:
            x1, c1, p1 = chars[index]
            x2, c2, p2 = chars[index + 1]
            # Collapse repeated neighbors only when one is clearly weaker.
            if c1 == c2 and (x2 - x1) <= (0.72 * med_gap) and abs(p1 - p2) >= 0.18:
                if p1 <= p2:
                    chars.pop(index)
                else:
                    chars.pop(index + 1)
                changed = True
                break
            index += 1
        if changed:
            continue

        # Rule 2: remove weak interior insertion tightly attached to neighbors.
        for index in range(1, len(chars) - 1):
            x_prev, _c_prev, p_prev = chars[index - 1]
            x_cur, _c_cur, p_cur = chars[index]
            x_next, _c_next, p_next = chars[index + 1]
            gap_prev = x_cur - x_prev
            gap_next = x_next - x_cur

            if min(gap_prev, gap_next) <= (0.72 * med_gap) and p_cur + 0.12 <= min(p_prev, p_next):
                chars.pop(index)
                changed = True
                break

    # Keep a final tail-noise guard for short attached duplicate endings.
    if len(chars) >= 2:
        med_gap = median_gap(chars)
        if med_gap > 0:
            last_gap = chars[-1][0] - chars[-2][0]
            last_char = chars[-1][1]
            last_conf = chars[-1][2]
            prior_chars = {entry[1] for entry in chars[:-1]}
            if last_gap <= (0.6 * med_gap) and last_char in prior_chars and last_conf <= (chars[-2][2] + 0.02):
                chars = chars[:-1]

    return "".join([entry[1] for entry in chars])


def solve_captcha_from_image(image: Image.Image) -> str:
    tuning = _load_tuning()
    conf_threshold = float(tuning.get("conf_threshold", 0.5))
    merge_distance = float(tuning.get("merge_distance", 8.0))
    min_length = int(tuning.get("min_length", 3))
    max_length = int(tuning.get("max_length", 6))
    plausible_length_bonus = float(tuning.get("plausible_length_bonus", 0.02))
    close_score_delta = float(tuning.get("close_score_delta", 0.02))
    preferred_variant_order = list(tuning.get("preferred_variant_order", []))
    variant_weights_raw = tuning.get("variant_weights", {})
    variant_weights = variant_weights_raw if isinstance(variant_weights_raw, dict) else {}
    variant_results: list[dict[str, object]] = []

    for variant_name, variant_image in _prepare_variants(image).items():
        text, score, picked = _decode_with_postprocess(
            variant_image,
            conf_threshold=conf_threshold,
            merge_distance=merge_distance,
        )
        if not text:
            continue

        avg_confidence = score / max(len(text), 1)
        weighted_conf = avg_confidence * float(variant_weights.get(variant_name, 1.0))
        if min_length <= len(text) <= max_length:
            weighted_conf += plausible_length_bonus
        variant_results.append(
            {
                "variant": variant_name,
                "text": text,
                "score": score,
                "avg_conf": avg_confidence,
                "weighted_conf": weighted_conf,
                "picked": picked,
            }
        )

    if variant_results:
        chosen = max(variant_results, key=lambda item: float(item["weighted_conf"]))
        chosen_text = str(chosen["text"])
        chosen_avg = float(chosen["avg_conf"])
        chosen_weighted = float(chosen["weighted_conf"])

        # When the top candidate is over-length, prefer a plausible-length candidate
        # if its confidence is close enough.
        if len(chosen_text) > 6:
            plausible = [
                item
                for item in variant_results
                if 3 <= len(str(item["text"])) <= 6
            ]
            if plausible:
                alt = max(plausible, key=lambda item: float(item["avg_conf"]))
                if float(alt["avg_conf"]) >= chosen_avg - 0.12:
                    chosen = alt
                    chosen_text = str(chosen["text"])
                    chosen_avg = float(chosen["avg_conf"])
                    chosen_weighted = float(chosen.get("weighted_conf", chosen_avg))

        # Lean/bold confusion: if two same-length candidates are very close,
        # trust a tuned variant preference order.
        if preferred_variant_order:
            same_length_close = [
                item
                for item in variant_results
                if len(str(item["text"])) == len(chosen_text)
                and abs(float(item["weighted_conf"]) - chosen_weighted) <= close_score_delta
            ]
            if len(same_length_close) >= 2:
                rank = {name: idx for idx, name in enumerate(preferred_variant_order)}
                chosen = min(same_length_close, key=lambda item: rank.get(str(item["variant"]), 999))
                chosen_text = str(chosen["text"])
                chosen_avg = float(chosen["avg_conf"])
                chosen_weighted = float(chosen["weighted_conf"])

        # Handle one-character insertion noise (e.g., ABCDX -> ABCD) when confidence is close.
        if len(chosen_text) == 5:
            len4_candidates = [
                item for item in variant_results if len(str(item["text"])) == 4
            ]
            for alt in sorted(len4_candidates, key=lambda item: float(item["avg_conf"]), reverse=True):
                alt_text = str(alt["text"])
                if float(alt["avg_conf"]) < chosen_avg - 0.03:
                    continue

                for index in range(len(chosen_text)):
                    if chosen_text[:index] + chosen_text[index + 1 :] == alt_text:
                        chosen = alt
                        chosen_text = alt_text
                        break
                if str(chosen["text"]) == alt_text:
                    break

        picked = chosen.get("picked", [])
        if isinstance(picked, list) and picked:
            return _prune_noise_chars(picked)

        return str(chosen["text"])

    fallback_text, _, fallback_picked = _decode_with_postprocess(
        image,
        conf_threshold=0.0,
        merge_distance=8.0,
    )
    if fallback_picked:
        return _prune_noise_chars(fallback_picked)
    return fallback_text


def solve_captcha(url: str) -> str:
    resp = requests.get(url, timeout=20)
    if resp.status_code != 200:
        raise RuntimeError("Encountered an error while downloading captcha image")

    image_buffer = BytesIO(resp.content)
    image = Image.open(image_buffer)
    return solve_captcha_from_image(image)
