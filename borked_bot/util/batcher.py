import logging
import random

def batcher(generator, batch_func, batch_size, shuffle=False):
    buf = []

    if shuffle:
        generator = list(generator)
        random.shuffle(generator)
    
    for item in generator:
        buf.append(item)
        if len(buf) >= batch_size:
            output = batch_func(buf)
            for item in buf:
                yield (item, output)
            buf = []
    if buf:
        output = None
        try:
            output = batch_func(buf)
        except:
            logging.exception("batch function failed!")

        if output:
            for item in buf:
                yield (item, output)

