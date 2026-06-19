from geoalchemy2.shape import to_shape


def boundary_to_coords(boundary) -> list[list[float]] | None:
    """Convert a PostGIS geography/geometry boundary to a list of [lon, lat] pairs."""
    if boundary is None:
        return None
    try:
        shape = to_shape(boundary)
        coords = list(shape.exterior.coords)
        return [[lon, lat] for lon, lat in coords]
    except Exception:
        return None
