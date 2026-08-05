from types import SimpleNamespace

from kikit.drc import DrcExclusion, serializeExclusion


def item_with_uuid(uuid_value):
    return SimpleNamespace(
        m_Uuid=SimpleNamespace(AsString=lambda: uuid_value)
    )


def test_serializeExclusionSortsCourtyardOverlapItemsByUuid():
    exclusion = DrcExclusion(
        "courtyards_overlap",
        (10, 20),
        [item_with_uuid("bbbbbbbb"), item_with_uuid("aaaaaaaa")]
    )

    assert serializeExclusion(exclusion) == (
        "courtyards_overlap|10|20|aaaaaaaa|bbbbbbbb"
    )


def test_serializeExclusionPreservesItemOrderForOtherViolations():
    exclusion = DrcExclusion(
        "clearance",
        (10, 20),
        [item_with_uuid("bbbbbbbb"), item_with_uuid("aaaaaaaa")]
    )

    assert serializeExclusion(exclusion) == (
        "clearance|10|20|bbbbbbbb|aaaaaaaa"
    )
