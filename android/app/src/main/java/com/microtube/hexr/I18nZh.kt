package com.microtube.hexr

/**
 * The Chinese for every English sentence the app shows through [tr]. Keyed by the English, which
 * stays the source of truth: change the English, and I18nTest says this needs the new key.
 */
internal val ZH: Map<String, String> = mapOf(
    // -- quick test
    "All good" to "全部良好",
    "{n} poor" to "{n} 个偏弱",
    "{n} failed" to "{n} 个失效",
    "Pump failed" to "气泵故障",
    "{good} good, {poor} poor, {failed} failed" to "{good} 个良好，{poor} 个偏弱，{failed} 个失效",
    "The source never rose above {kpa} kPa, so no channel could have reached pressure. This is one fault in the pump or its supply, not six failed channels." to
        "气源始终未超过 {kpa} kPa，因此任何通道都无法达到压力。这是气泵或其供气的一处故障，而不是六个通道都失效。",
    "The source reached {kpa} kPa, so supply is fine: a channel reading nothing with a healthy source is a blocked line, a valve that never opened, or a dead indenter." to
        "气源达到 {kpa} kPa，供气正常：气源正常而通道没有读数，说明管路堵塞、阀门没有打开，或压头损坏。",
    "The source reached {kpa} kPa. Every channel moved, but not all of them reached full pressure: check the tubing on the weak ones." to
        "气源达到 {kpa} kPa。每个通道都有动作，但并非全部达到满压：请检查偏弱通道的气管。",
    "The source reached {kpa} kPa." to "气源达到 {kpa} kPa。",
)
