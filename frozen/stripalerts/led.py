def deg_to_rgb(deg):
    """Convert degrees (Hue) to RGB colour (0-255).

    Args:
        deg (int): Degree value from 0 to 360 (Hue).

    Returns:
        tuple: RGB colour as a tuple of three integers from 0 to 255.
    """
    deg = deg % 360

    # Sector 0 to 5
    region = deg // 60

    # We want 0..255 for the calculation
    # p, q, t calculation for V=1, S=1 in HSV logic
    # But since we just want a simple rainbow, we can do linear interpolation
    # RGB Range 0-255

    # Fully saturated colors (S=1, V=1)
    val = 255
    # rising/falling slope
    x = int(val * (deg % 60) / 60)

    if region == 0:
        return (val, x, 0)
    elif region == 1:
        return (val - x, val, 0)
    elif region == 2:
        return (0, val, x)
    elif region == 3:
        return (0, val - x, val)
    elif region == 4:
        return (x, 0, val)
    else:  # region 5
        return (val, 0, val - x)
