from types import SimpleNamespace

import pytest

from kikit.defs import Layer
from kikit.panel_features.copperFill import (
    HatchedCopperFill, HexCopperFill, SolidCopperFill
)
from kikit.panelize_ui_impl import *


class FakeEnabledLayers:
    def __init__(self, layers):
        self.layers = set(layers)

    def Contains(self, layer):
        return layer in self.layers


class FakeCopperfillPanel:
    def __init__(self, enabledLayers):
        self.board = SimpleNamespace(
            GetEnabledLayers=lambda: FakeEnabledLayers(enabledLayers)
        )
        self.feature = None

    def apply(self, feature):
        self.feature = feature


def copperfillPreset(type, layers):
    return {
        "type": type,
        "clearance": 1,
        "edgeclearance": 1,
        "layers": layers,
        "width": 1,
        "spacing": 1,
        "orientation": 0,
        "diameter": 1,
        "threshold": 0.25,
    }


@pytest.mark.parametrize("type, featureType", [
    ("solid", SolidCopperFill),
    ("hatched", HatchedCopperFill),
    ("hex", HexCopperFill),
])
def test_copperfillAllUsesOnlyProjectLayers(type, featureType):
    panel = FakeCopperfillPanel([Layer.F_Cu, Layer.In1_Cu, Layer.B_Cu])

    buildCopperfill(copperfillPreset(type, "all"), panel)

    assert isinstance(panel.feature, featureType)
    assert panel.feature.layers == [Layer.F_Cu, Layer.B_Cu, Layer.In1_Cu]


def test_copperfillExplicitLayerIsNotFiltered():
    panel = FakeCopperfillPanel([Layer.F_Cu, Layer.B_Cu])

    buildCopperfill(copperfillPreset("hex", [Layer.In1_Cu]), panel)

    assert panel.feature.layers == [Layer.In1_Cu]


def test_copperfillAllShortcutSurvivesPresetRoundtrip():
    section = COPPERFILL_SECTION["layers"]

    assert section.validate("all") == "all"
    assert encodePreset(section.validate("all")) == "all"


def test_presetLayout():
    with pytest.raises(PresetError):
        validatePresetLayout([])
    validatePresetLayout({})
    with pytest.raises(PresetError):
        validatePresetLayout({"a": []})
    validatePresetLayout({"a": {"b": 43}})

def test_merge():
    # Merge into empty
    a = {}
    mergePresets(a, {"a": {}})
    assert a == {"a": {}}

    mergePresets(a, {"a": {
        "value": 42,
        "otherValue": 70
    }})
    assert a == {"a": {
        "value": 42,
        "otherValue": 70
    }}

    mergePresets(a, {"a": {
        "value": 43
    }})
    assert a == {"a": {
        "value": 43,
        "otherValue": 70
    }}
