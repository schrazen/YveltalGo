import React, { useState } from "react";
import { CogIcon, CheckIcon, WarningIcon } from "../Icons.jsx";

export default function ConfigView({
  configJson,
  setConfigJson,
  configDirty,
  setConfigDirty,
  onSaveConfig,
  onFormatConfig,
  busyAction,
  configPath,
}) {
  const [editorMode, setEditorMode] = useState("visual");
  const [saveSuccess, setSaveSuccess] = useState(false);

  let parsedConfig = {};
  try {
    parsedConfig = JSON.parse(configJson || "{}");
  } catch {
    // raw invalid JSON handled
  }

  const handleFieldChange = (section, field, value) => {
    try {
      const current = JSON.parse(configJson || "{}");
      if (section) {
        current[section] = current[section] || {};
        current[section][field] = value;
      } else {
        current[field] = value;
      }
      setConfigJson(JSON.stringify(current, null, 2));
      setConfigDirty(true);
    } catch (e) {
      console.error(e);
    }
  };

  const handleSave = async () => {
    await onSaveConfig();
    setSaveSuccess(true);
    setTimeout(() => setSaveSuccess(false), 2500);
  };

  return (
    <div className="space-y-4">
      {/* Top Header Card */}
      <div className="glass-panel p-5 rounded-2xl border border-rose-950/40 shadow-xl flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h3 className="text-base font-bold text-white flex items-center gap-2">
            <CogIcon className="w-4 h-4 text-rose-500" />
            <span>Application Settings & Configuration</span>
          </h3>
          <p className="text-xs text-slate-400 mt-0.5 font-mono">
            {configPath || "config.json"} • {configDirty ? "⚠️ Unsaved changes" : "✅ Synced with disk"}
          </p>
        </div>

        <div className="flex items-center gap-2">
          {/* Mode Switcher */}
          <div className="flex bg-slate-900 p-1 rounded-xl border border-slate-800 text-xs font-bold">
            <button
              onClick={() => setEditorMode("visual")}
              className={`px-3 py-1 rounded-lg transition-all ${
                editorMode === "visual" ? "bg-rose-600 text-white" : "text-slate-400 hover:text-white"
              }`}
            >
              Form Editor
            </button>
            <button
              onClick={() => setEditorMode("json")}
              className={`px-3 py-1 rounded-lg transition-all ${
                editorMode === "json" ? "bg-rose-600 text-white" : "text-slate-400 hover:text-white"
              }`}
            >
              Raw JSON
            </button>
          </div>

          <button
            onClick={onFormatConfig}
            className="px-3 py-1.5 rounded-xl text-xs font-bold bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700"
          >
            Format
          </button>

          <button
            onClick={handleSave}
            disabled={!configDirty || busyAction !== ""}
            className="px-4 py-1.5 rounded-xl text-xs font-bold bg-rose-600 hover:bg-rose-500 text-white shadow-md transition-all disabled:opacity-40 flex items-center gap-1.5"
          >
            {saveSuccess ? <CheckIcon className="w-3.5 h-3.5 text-white" /> : null}
            <span>{saveSuccess ? "Saved!" : "Save Changes"}</span>
          </button>
        </div>
      </div>

      {/* Visual Form Editor */}
      {editorMode === "visual" && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {/* Section 1: Security & Server Lock */}
          <div className="glass-panel p-5 rounded-2xl border border-rose-950/40 shadow-xl space-y-3.5">
            <h4 className="text-sm font-bold text-white uppercase tracking-wider flex items-center gap-2">
              <span>🛡️ Security & Server Firewall</span>
            </h4>

            <div>
              <label className="text-xs font-bold text-slate-300 block mb-1">
                RequiredServerID (Discord Guild Lock)
              </label>
              <input
                type="number"
                value={parsedConfig.RequiredServerID || ""}
                onChange={(e) => handleFieldChange(null, "RequiredServerID", Number(e.target.value))}
                className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-1.5 text-xs text-white font-mono"
              />
              <p className="text-[10px] text-slate-400 mt-1">
                All bot actions are firewall-intercepted and strictly confined to this server ID.
              </p>
            </div>

            <div>
              <label className="text-xs font-bold text-slate-300 block mb-1">
                Suspicion Avoidance Score
              </label>
              <input
                type="number"
                value={parsedConfig.SuspicionAvoidance || 250}
                onChange={(e) => handleFieldChange(null, "SuspicionAvoidance", Number(e.target.value))}
                className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-1.5 text-xs text-white font-mono"
              />
            </div>
          </div>

          {/* Section 2: Delays & Pacing */}
          <div className="glass-panel p-5 rounded-2xl border border-rose-950/40 shadow-xl space-y-3.5">
            <h4 className="text-sm font-bold text-white uppercase tracking-wider flex items-center gap-2">
              <span>⏱️ Pacing & Delay Limits</span>
            </h4>

            <div className="grid grid-cols-2 gap-2.5">
              <div>
                <label className="text-xs font-bold text-slate-300 block mb-1">Hunting Min Delay (s)</label>
                <input
                  type="number"
                  value={parsedConfig.Delays?.HuntingDelayMin || 12}
                  onChange={(e) => handleFieldChange("Delays", "HuntingDelayMin", Number(e.target.value))}
                  className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-1.5 text-xs text-white font-mono"
                />
              </div>
              <div>
                <label className="text-xs font-bold text-slate-300 block mb-1">Hunting Max Delay (s)</label>
                <input
                  type="number"
                  value={parsedConfig.Delays?.HuntingDelayMax || 28}
                  onChange={(e) => handleFieldChange("Delays", "HuntingDelayMax", Number(e.target.value))}
                  className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-1.5 text-xs text-white font-mono"
                />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-2.5">
              <div>
                <label className="text-xs font-bold text-slate-300 block mb-1">Fishing Min Delay (s)</label>
                <input
                  type="number"
                  value={parsedConfig.Delays?.FishingDelayMin || 28}
                  onChange={(e) => handleFieldChange("Delays", "FishingDelayMin", Number(e.target.value))}
                  className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-1.5 text-xs text-white font-mono"
                />
              </div>
              <div>
                <label className="text-xs font-bold text-slate-300 block mb-1">Fishing Max Delay (s)</label>
                <input
                  type="number"
                  value={parsedConfig.Delays?.FishingDelayMax || 65}
                  onChange={(e) => handleFieldChange("Delays", "FishingDelayMax", Number(e.target.value))}
                  className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-1.5 text-xs text-white font-mono"
                />
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Raw JSON Editor */}
      {editorMode === "json" && (
        <div className="glass-panel p-5 rounded-2xl border border-rose-950/40 shadow-xl space-y-3">
          <textarea
            value={configJson}
            onChange={(e) => {
              setConfigJson(e.target.value);
              setConfigDirty(true);
            }}
            rows={22}
            className="w-full bg-black/80 font-mono text-xs text-slate-200 border border-slate-800 rounded-xl p-4 focus:outline-none focus:border-rose-500 leading-relaxed"
            spellCheck="false"
          />
        </div>
      )}
    </div>
  );
}
