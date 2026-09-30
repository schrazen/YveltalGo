import React from "react";
import { CloseIcon, PokeBallIcon, SparkleIcon, SpinnerIcon } from "./Icons.jsx";
import { toDisplayName, getFlavorText } from "../utils/helpers.js";

const TYPE_COLORS = {
  normal: "bg-stone-500/20 text-stone-300 border-stone-500/40",
  fire: "bg-orange-500/20 text-orange-300 border-orange-500/40",
  water: "bg-blue-500/20 text-blue-300 border-blue-500/40",
  grass: "bg-emerald-500/20 text-emerald-300 border-emerald-500/40",
  electric: "bg-amber-500/20 text-amber-300 border-amber-500/40",
  ice: "bg-cyan-500/20 text-cyan-300 border-cyan-500/40",
  fighting: "bg-red-700/20 text-red-300 border-red-700/40",
  poison: "bg-purple-600/20 text-purple-300 border-purple-600/40",
  ground: "bg-amber-700/20 text-amber-300 border-amber-700/40",
  flying: "bg-indigo-400/20 text-indigo-300 border-indigo-400/40",
  psychic: "bg-pink-600/20 text-pink-300 border-pink-600/40",
  bug: "bg-lime-600/20 text-lime-300 border-lime-600/40",
  rock: "bg-stone-600/20 text-stone-300 border-stone-600/40",
  ghost: "bg-purple-900/20 text-purple-300 border-purple-900/40",
  dragon: "bg-indigo-700/20 text-indigo-300 border-indigo-700/40",
  steel: "bg-slate-400/20 text-slate-300 border-slate-400/40",
  fairy: "bg-rose-400/20 text-rose-300 border-rose-400/40",
  dark: "bg-neutral-800/40 text-neutral-300 border-neutral-700/40",
};

export default function PokemonModal({
  selectedCatch,
  selectedPokemonInfo,
  selectedPokemonLoading,
  selectedPokemonError,
  onClose,
  pokemonFallbackPrompt,
  setPokemonFallbackPrompt,
  onApplyFallback,
  pokemonFallbackBusy,
}) {
  if (!selectedCatch) return null;

  const data = selectedPokemonInfo?.data;
  const species = selectedPokemonInfo?.species;
  const flavor = getFlavorText(species);

  return (
    <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-md flex items-center justify-center p-4">
      <div className="glass-panel-elevated rounded-2xl max-w-lg w-full p-5 space-y-4 border border-rose-950/60 shadow-2xl relative">
        <button
          onClick={onClose}
          className="absolute top-4 right-4 p-1.5 rounded-lg bg-slate-900 text-slate-400 hover:text-white border border-slate-800"
        >
          <CloseIcon className="w-4 h-4" />
        </button>

        {/* Header */}
        <div className="flex items-center gap-3">
          <div className="w-16 h-16 rounded-xl bg-black/60 border border-rose-950/60 flex items-center justify-center p-1 overflow-hidden shrink-0">
            {selectedCatch.sprite ? (
              <img
                src={selectedCatch.sprite}
                alt={selectedCatch.name}
                className="w-14 h-14 object-contain"
                style={{ imageRendering: "pixelated" }}
              />
            ) : (
              <PokeBallIcon className="w-8 h-8 text-rose-500" />
            )}
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h3 className="text-lg font-black text-white">{selectedCatch.name}</h3>
              <span className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider ${selectedCatch.badgeCls || "bg-rose-500/20 text-rose-300"}`}>
                {selectedCatch.rarity}
              </span>
            </div>
            <p className="text-xs text-slate-400 mt-0.5">
              Captured via PokéMeow • {selectedCatch.ball ? `Used ${selectedCatch.ball}` : "Recent Encounter"}
            </p>
          </div>
        </div>

        {/* Loading / Error States */}
        {selectedPokemonLoading && (
          <div className="p-8 text-center text-sm text-slate-400 flex items-center justify-center gap-2">
            <SpinnerIcon className="w-4 h-4 text-rose-400" />
            <span>Querying PokéAPI Database...</span>
          </div>
        )}

        {selectedPokemonError && !selectedPokemonLoading && (
          <div className="p-4 rounded-xl bg-amber-950/20 border border-amber-900/40 text-xs text-amber-300 space-y-2">
            <p>{selectedPokemonError}</p>
            <div className="flex items-center gap-2 pt-2 border-t border-amber-900/30">
              <input
                type="text"
                placeholder="Custom PokeAPI slug (e.g. mewtwo)"
                value={pokemonFallbackPrompt?.customSlug || ""}
                onChange={(e) => setPokemonFallbackPrompt((prev) => ({ ...prev, customSlug: e.target.value }))}
                className="bg-black/60 border border-amber-900/50 rounded-lg px-2.5 py-1 text-xs text-white flex-1"
              />
              <button
                onClick={onApplyFallback}
                disabled={pokemonFallbackBusy}
                className="px-3 py-1 rounded-lg bg-amber-600 hover:bg-amber-500 text-white font-bold text-xs"
              >
                Search
              </button>
            </div>
          </div>
        )}

        {/* PokéAPI Data Content */}
        {data && !selectedPokemonLoading && (
          <div className="space-y-3.5">
            {/* Type Badges */}
            <div className="flex items-center gap-2">
              {data.types?.map((t, i) => {
                const typeName = t?.type?.name || "";
                const cls = TYPE_COLORS[typeName] || "bg-slate-800 text-slate-300 border-slate-700";
                return (
                  <span
                    key={i}
                    className={`px-2.5 py-1 rounded-lg text-[10px] font-black uppercase tracking-wider border ${cls}`}
                  >
                    {typeName}
                  </span>
                );
              })}
              <span className="ml-auto text-xs font-mono text-slate-400">
                #{String(data.id || 0).padStart(3, "0")}
              </span>
            </div>

            {/* Flavor Text */}
            {flavor && (
              <p className="text-xs text-slate-300 italic p-3 rounded-xl bg-black/40 border border-rose-950/40 leading-relaxed">
                "{flavor}"
              </p>
            )}

            {/* Base Stats Grid */}
            <div className="space-y-2">
              <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400 block">
                Base Battle Attributes
              </span>
              <div className="grid grid-cols-2 gap-2 text-xs">
                {data.stats?.map((st, i) => {
                  const statName = toDisplayName(st?.stat?.name || "");
                  const baseVal = st?.base_stat || 0;
                  const percent = Math.min(100, Math.round((baseVal / 255) * 100));
                  return (
                    <div key={i} className="p-2 rounded-lg bg-slate-900/70 border border-slate-800">
                      <div className="flex justify-between text-[11px] mb-1">
                        <span className="text-slate-400 font-semibold">{statName}</span>
                        <span className="font-mono font-bold text-white">{baseVal}</span>
                      </div>
                      <div className="w-full bg-slate-800 rounded-full h-1.5 overflow-hidden">
                        <div
                          className="bg-gradient-to-r from-rose-500 to-amber-400 h-full rounded-full"
                          style={{ width: `${percent}%` }}
                        />
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
