from collections import defaultdict


# XXX/TODO: needs documentation/a better name
class mydefaultdict(defaultdict):
    def __missing__(self, key):
        if self.default_factory is None:
            raise KeyError(key)
        else:
            value = self[key] = self.default_factory(key)
            return value
