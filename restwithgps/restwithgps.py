from __future__ import annotations
from typing import Generator, Optional
from dataclasses import dataclass
import datetime
from math import sin, cos, acos, radians, atan2
import json

import fitparse
import folium

TO_DEGREE = 180.0 / (2**31)
POINT_INTERVAL_TIME = datetime.timedelta(seconds=10)
MIN_SPEED = 5.0
MIN_STOP = datetime.timedelta(minutes=5)
TIME_ZONE_DIFF = datetime.timedelta(hours=2)

earth_rad = 6378.137


@dataclass
class StopPoint:
    latitude: float
    longitude: float
    start_time: datetime.datetime
    end_time: datetime.datetime


@dataclass
class Point:
    timestamp: datetime.datetime
    latitude: float
    longitude: float


def to_degree(semicircle: int) -> float:
    return semicircle * TO_DEGREE


def _latlng_to_xyz(lat: float, lng: float) -> tuple[float, float, float]:
    rlat, rlng = radians(lat), radians(lng)
    coslat = cos(rlat)
    return coslat * cos(rlng), coslat * sin(rlng), sin(rlat)


def get_distance(pos0: tuple[float, float], pos1: tuple[float, float], radious: float = earth_rad) -> float:
    if pos0 == pos1:
        return 0.0
    # print(pos0, pos1)
    xyz0, xyz1 = _latlng_to_xyz(*pos0), _latlng_to_xyz(*pos1)
    # print(xyz0, xyz1)
    try:
        return acos(sum(x * y for x, y in zip(xyz0, xyz1))) * radious
    except ValueError:
        return 0.0


def get_speed(km: float, second: float) -> float:
    return km / second * 3600


def get_vector(pos0: tuple[float, float], pos1: tuple[float, float]) -> float:
    return atan2(pos1[0] - pos0[0], pos1[1] - pos0[1])


class AbstractPointStream(object):
    def __init__(self, filepath: str) -> None:
        self.filepath = filepath
        self._prev_timestamp: Optional[datetime.datetime] = None
        self._points: list[Point] = []

    def _get_point(self) -> Generator[Point, None, None]:
        pass

    def get_point(self) -> Generator[Point, None, None]:
        for point in self._get_point():
            if not self._points or (point.timestamp - self._points[0].timestamp) < POINT_INTERVAL_TIME:
                self._points.append(point)
            else:
                yield Point(
                    self._points[0].timestamp,
                    sum([_.latitude for _ in self._points]) / len(self._points),
                    sum([_.longitude for _ in self._points]) / len(self._points),
                )
                self._points = [point]

        if self._points:
            yield Point(
                self._points[0].timestamp,
                sum([_.latitude for _ in self._points]) / len(self._points),
                sum([_.longitude for _ in self._points]) / len(self._points),
            )


class PointStreamFit(AbstractPointStream):
    def _get_point(self) -> Generator[Point, None, None]:
        ff = fitparse.FitFile(self.filepath)
        for record in ff.get_messages("record"):
            point_dict: dict[str, int | float | str | datetime.datetime] = {}
            for data in record:
                if data.units == "semicircles":
                    data.units = "degrees"
                    if data.value is None:
                        continue
                    data.value = to_degree(data.value)

                point_dict[data.name] = data.value

            if "position_lat" in point_dict and "position_long" in point_dict:
                yield Point(
                    point_dict["timestamp"],
                    point_dict["position_lat"],
                    point_dict["position_long"]
                )


class PointStreamStrava(AbstractPointStream):
    def _get_point(self) -> Generator[Point, None, None]:
        with open(self.filepath, "r") as f:
            data = json.load(f)

        for item in data:
            if item["type"] == "latlng":
                latlngs = item["data"]
            elif item["type"] == "time":
                timestamps = item["data"]

        for timestamp, latlng in zip(timestamps, latlngs):
            yield Point(
                datetime.datetime(2023, 8, 20, 20, 30) + datetime.timedelta(seconds=timestamp),
                latlng[0],
                latlng[1]
            )


def get_speed_from_points(point1: Point, point2: Point) -> float:
    km = get_distance(
        (point1.latitude, point1.longitude),
        (point2.latitude, point2.longitude))
    second = (point2.timestamp - point1.timestamp).seconds
    speed = get_speed(km, second)

    return speed


def get_stop_points(point_stream: AbstractPointStream) -> tuple[list[StopPoint], list[tuple[float, float]]]:
    stop_points: list[StopPoint] = []
    stop_point: Optional[StopPoint] = None
    prev_point: Optional[Point] = None
    route: list[tuple[float, float]] = []
    prev_vector: float = 0

    for point in point_stream.get_point():
        if prev_point:
            speed = get_speed_from_points(prev_point, point)
            if speed < MIN_SPEED:  # Stopping
                if stop_point:
                    # If already stopped, extend stop time
                    stop_point.end_time = point.timestamp + TIME_ZONE_DIFF
                else:
                    stop_point = StopPoint(
                        point.latitude,
                        point.longitude,
                        point.timestamp + TIME_ZONE_DIFF,
                        point.timestamp + TIME_ZONE_DIFF,
                    )

            else:  # Moving
                if stop_point:
                    stop_points.append(stop_point)
                    stop_point = None

            vector = get_vector((prev_point.latitude, prev_point.longitude),
                                (point.latitude, point.longitude))
            if abs(vector - prev_vector) >= 0.1:
                route.append((point.latitude, point.longitude))

            prev_vector = vector

        else:
            route.append((point.latitude, point.longitude))

        prev_point = point

    return stop_points, route


def _draw_route(map: folium.Map, route: list[tuple[float, float]]) -> None:
    folium.PolyLine(route, color="#e4007f").add_to(map)


def get_elapsed_time(stop_point: StopPoint) -> int:
    elapsed_time = int((stop_point.end_time - stop_point.start_time).seconds / 60 + 0.5)

    return elapsed_time


def elapsed_time_to_str(elapsed_time: int) -> str:
    if elapsed_time >= 60:
        s_elapsed_time = f"{int(elapsed_time / 60)}h {elapsed_time % 60}m"
    else:
        s_elapsed_time = f"{elapsed_time}m"

    return s_elapsed_time


def _mark_stops(map: folium.Map, stop_points: list[StopPoint]) -> None:
    for stop_point in stop_points:
        if stop_point.end_time - stop_point.start_time < MIN_STOP:
            continue

        start_time = stop_point.start_time.strftime("%d/%H:%M")
        end_time = stop_point.end_time.strftime("%d/%H:%M")
        elapsed_time = get_elapsed_time(stop_point)
        s_elapsed_time = elapsed_time_to_str(elapsed_time)

        googlemap = f"https://maps.google.co.jp/maps?q={stop_point.latitude},{stop_point.longitude}"
        googlemap_link = f'<a href="{googlemap}" target="_blank" rel="noopener noreferrer">googlemap</a>'

        popup = folium.Popup(f"{start_time}-{end_time}\n{s_elapsed_time} {googlemap_link}",
                             show=False)

        folium.Marker(location=[stop_point.latitude, stop_point.longitude],
                      popup=popup
                      ).add_to(map)

        folium.CircleMarker(
            location=[stop_point.latitude, stop_point.longitude],
            color="#00aa00",
            radius=elapsed_time / 4
        ).add_to(map)


def get_center_of_route(route: list[tuple[float, float]]) -> tuple[float, float]:
    lats = [_[0] for _ in route]
    longs = [_[1] for _ in route]

    return ((min(lats) + max(lats)) / 2, (min(longs) + max(longs)) / 2)


def get_bounds_of_route(route: list[tuple[float, float]]) -> tuple[tuple[float, float], tuple[float, float]]:
    lats = [_[0] for _ in route]
    longs = [_[1] for _ in route]

    return ((min(lats), min(longs)), (max(lats), max(longs)))


def draw_map(stop_points: list[StopPoint], route: list[tuple[float, float]], filepath="map"):
    center_location = get_center_of_route(route)
    # map = folium.Map(location=center_location, zoom_start=8)
    map = folium.Map()
    map.fit_bounds(get_bounds_of_route(route))

    _draw_route(map, route)
    _mark_stops(map, stop_points)

    map.save(filepath + ".html")


def rest_with_gps(filepath: str) -> str:
    point_stream = PointStreamFit(filepath)
    # point_stream = PointStreamStrava("ma-tana.fit")

    stop_points, route = get_stop_points(point_stream)

    draw_map(stop_points, route, filepath)
