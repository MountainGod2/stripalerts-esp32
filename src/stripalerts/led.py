def deg_to_rgb(deg):
    """Convert degrees to RGB colour.

    Args:
        deg (int): Degree value from 0 to 360.

    Returns:
        tuple: RGB colour as a tuple of three floats from 0 to 1.
    """
    deg=deg%360
    m=1/60
    R=0
    G=0
    B=0

    if deg>=0 and deg<60:
        R=1
        G=0
        B=m*deg
    if deg>=60 and deg<120:
        R=1-m*(deg-60)
        G=0
        B=1
    if deg>=120 and deg<180:
        R=0
        G=m*(deg-120)
        B=1
    if deg>=180 and deg<240:
        R=0
        G=1
        B=1-m*(deg-180)
    if deg>=240 and deg<300:
        R=m*(deg-240)
        G=1
        B=0
    if deg>=300 and deg<360:
        R=1
        G=1-m*(deg-300)
        B=0
    my_colour=(R,G,B)
    return my_colour
