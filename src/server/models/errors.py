class UnknownEmployee(LookupError):
    pass


class UnknownRole(LookupError):
    pass


class UnknownReview(LookupError):
    pass


class ReviewAlreadyResolved(ValueError):
    pass


class InvalidField(ValueError):
    pass
