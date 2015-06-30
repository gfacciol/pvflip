#import collections
import recipe_576693_1 as collections

class LRUCache:
    def __init__(self, capacity):
        self.capacity = capacity
        self.cache = collections.OrderedDict()
        # initialize all the values (texture id) with a dummy key
        for t in range(1,capacity+1):
           self.cache[t] = t


    def get(self, key):
        try:
            value = self.cache.pop(key)
            self.cache[key] = value
            return value
        except KeyError:
            return -1

    def set(self, key):
        value = -1;
        try:
            value = self.cache.pop(key)
        except KeyError:
            if len(self.cache) >= self.capacity:
                value = self.cache.popitem(last=False)[1]
        self.cache[key] = value
        return value
