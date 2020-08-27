def z_order_hash(row, col):
    # https://stackoverflow.com/a/682481
    return ( row << 16 ) ^ col
