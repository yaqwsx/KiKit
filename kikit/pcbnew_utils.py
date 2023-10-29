from pcbnewTransition import pcbnew


def increaseZonePriorities(board: pcbnew.BOARD, amount: int = 1):
    """
    Given a board, increase priority of all zones by given amount
    """
    for zone in board.Zones():
        zone.SetAssignedPriority(zone.GetAssignedPriority() + amount)
