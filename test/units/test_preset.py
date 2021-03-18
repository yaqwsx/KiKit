import pytest
from kikit.panelize_ui_impl import *

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