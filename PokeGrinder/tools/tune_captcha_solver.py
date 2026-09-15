import json
from itertools import permutations
from pathlib import Path
import sys

from PIL import Image

BASE_DIR = Path(__file__).resolve().parents[1]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from modules import captcha_solver as solver

DATASET_PATH = BASE_DIR / "assets" / "captcha_samples" / "training_dataset.jsonl"
OUTPUT_TUNING_PATH = BASE_DIR / "assets" / "captcha_samples" / "solver_tuning.json"


def _load_rows() -> list[dict]:
    rows: list[dict] = []
    for line in DATASET_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        record = json.loads(line)
        image_path = BASE_DIR / str(record.get("image_path", ""))
        label = str(record.get("label", "")).strip()
        if not image_path.exists() or not label:
            continue
        rows.append({"image_path": image_path, "label": label})
    return rows


def _predict_with_tuning(precomputed: list[dict[str, object]], tuning: dict[str, object]) -> str:
    min_length = int(tuning["min_length"])
    max_length = int(tuning["max_length"])
    plausible_length_bonus = float(tuning["plausible_length_bonus"])
    close_score_delta = float(tuning["close_score_delta"])
    preferred_variant_order = list(tuning["preferred_variant_order"])
    variant_weights = dict(tuning["variant_weights"])

    variant_results: list[dict[str, object]] = []
    for item in precomputed:
        variant_name = str(item["variant"])
        text = str(item["text"])
        score = float(item["score"])
        picked = item.get("picked", [])
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
                "avg_conf": avg_confidence,
                "weighted_conf": weighted_conf,
                "picked": picked,
            }
        )

    if not variant_results:
        return ""

    chosen = max(variant_results, key=lambda item: float(item["weighted_conf"]))
    chosen_text = str(chosen["text"])
    chosen_weighted = float(chosen["weighted_conf"])
    chosen_avg = float(chosen["avg_conf"])

    if len(chosen_text) > max_length:
        plausible = [
            item for item in variant_results if min_length <= len(str(item["text"])) <= max_length
        ]
        if plausible:
            alt = max(plausible, key=lambda item: float(item["avg_conf"]))
            if float(alt["avg_conf"]) >= chosen_avg - 0.12:
                chosen = alt
                chosen_text = str(chosen["text"])
                chosen_weighted = float(chosen.get("weighted_conf", chosen_avg))

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

    if len(chosen_text) == 5:
        len4_candidates = [item for item in variant_results if len(str(item["text"])) == 4]
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
        return solver._prune_noise_chars(picked)
    return chosen_text


def _evaluate(rows: list[dict], tuning: dict[str, object]) -> tuple[int, list[dict]]:
    correct = 0
    details: list[dict] = []
    for row in rows:
        predicted = _predict_with_tuning(row["precomputed"], tuning)
        expected = row["label"]
        ok = predicted == expected
        if ok:
            correct += 1
        details.append(
            {
                "file": row["image_path"].name,
                "prediction": predicted,
                "expected": expected,
                "correct": ok,
            }
        )
    return correct, details


def main() -> None:
    rows = _load_rows()
    if not rows:
        raise RuntimeError("No usable rows found in training dataset.")

    conf_threshold = 0.5
    merge_distance = 8.0
    for row in rows:
        image = Image.open(row["image_path"])
        precomputed: list[dict[str, object]] = []
        for variant_name, variant_image in solver._prepare_variants(image).items():
            text, score, picked = solver._decode_with_postprocess(
                variant_image,
                conf_threshold=conf_threshold,
                merge_distance=merge_distance,
            )
            precomputed.append(
                {
                    "variant": variant_name,
                    "text": text,
                    "score": score,
                    "picked": picked,
                }
            )
        row["precomputed"] = precomputed

    variant_names = ["th120_med", "th135_open2", "raw", "th120"]
    best_tuning = None
    best_correct = -1
    best_details: list[dict] = []

    # Keep decode parameters fixed to avoid extremely expensive YOLO re-runs.
    # This tuning pass focuses on close-call ranking and variant preference.
    for close_delta in [0.015, 0.02, 0.025, 0.03]:
        for plausible_bonus in [0.01, 0.02, 0.03]:
            for order in permutations(variant_names):
                tuning = {
                    "conf_threshold": conf_threshold,
                    "merge_distance": merge_distance,
                    "min_length": 3,
                    "max_length": 6,
                    "plausible_length_bonus": plausible_bonus,
                    "variant_weights": {name: 1.0 for name in variant_names},
                    "close_score_delta": close_delta,
                    "preferred_variant_order": list(order),
                }
                correct, details = _evaluate(rows, tuning)
                if correct > best_correct:
                    best_correct = correct
                    best_tuning = tuning
                    best_details = details

    assert best_tuning is not None
    OUTPUT_TUNING_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_TUNING_PATH.write_text(json.dumps(best_tuning, indent=2), encoding="utf-8")

    report = {
        "dataset_rows": len(rows),
        "correct": best_correct,
        "accuracy": best_correct / max(len(rows), 1),
        "tuning_file": str(OUTPUT_TUNING_PATH.relative_to(BASE_DIR)).replace("\\", "/"),
        "best_tuning": best_tuning,
        "rows": best_details,
    }
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
