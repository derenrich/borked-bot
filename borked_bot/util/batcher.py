


def batcher(generator, batch_func, batch_size):
    buf = []
    for item in generator:
        buf.append(item)
        if len(buf) >= batch_size:
            output = batch_func(buf)
            for item in buf:
                yield (item, output)
            buf = []
    if buf:
        output = batch_func(buf)
        for item in buf:
            yield (item, output)
