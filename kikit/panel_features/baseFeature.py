from ..panelize import Panel

class PanelFeature:
    """
    Basic interface for various
    """
    def apply(self, panel: Panel) -> None:
        raise NotImplementedError("Implementation error: PanelFeature doesn't support applying")
