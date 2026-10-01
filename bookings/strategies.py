class PassStrategy:
    """Interface: how one kind of pass answers the three questions."""
    type_name = ""
    priority = 0  # lower number = used first when a member has several passes

    def is_valid(self, pass_row, now):
        raise NotImplementedError

    def remaining_after_use(self, pass_row):
        raise NotImplementedError

    def remaining_after_refund(self, pass_row):
        raise NotImplementedError

# Checks if a pass has passed its expiration date 
def _not_expired(pass_row, now):
    expires_at = pass_row["expires_at"]
    return expires_at is None or expires_at > now.isoformat(timespec="seconds")


class UsesBasedStrategy(PassStrategy):
    """Shared behaviour for passes that count down: drop-in and class pack."""

    def is_valid(self, pass_row, now):
        remaining = pass_row["remaining_uses"]
        return remaining is not None and remaining > 0 and _not_expired(pass_row, now)

    def remaining_after_use(self, pass_row):
        return pass_row["remaining_uses"] - 1

    def remaining_after_refund(self, pass_row):
        return pass_row["remaining_uses"] + 1


class DropInStrategy(UsesBasedStrategy):
    type_name = "drop_in"
    priority = 2


class ClassPackStrategy(UsesBasedStrategy):
    type_name = "class_pack"
    priority = 1


class MembershipStrategy(PassStrategy):
    type_name = "membership"
    priority = 0

    def is_valid(self, pass_row, now):
        return _not_expired(pass_row, now)

    def remaining_after_use(self, pass_row):
        return None  # unlimited: stays NULL

    def remaining_after_refund(self, pass_row):
        return None


STRATEGIES = { 
    #STRATEGIES dictionary holds "drop_in" mapped to an actual DropInStrategy object. 
    # Does for all strats so you can get it in get_strategy(): return STRATEGIES[type_name] 
    s.type_name: s
    for s in (DropInStrategy(), ClassPackStrategy(), MembershipStrategy())
}


def get_strategy(type_name):
    try:
        return STRATEGIES[type_name]
    except KeyError:
        raise ValueError(f"Unknown pass type: {type_name}")