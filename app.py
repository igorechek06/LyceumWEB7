import sys
from math import atan2, cos, radians, sin, sqrt

import requests
from PyQt5 import QtCore, QtGui, QtWidgets
from rich import print

from ui.main import Ui_MainWindow

R = 6378100
static_key = "40d1649f-0493-4b70-98ba-98533de7710b"
static_url = "https://static-maps.yandex.ru/1.x/"

geocode_key = "40d1649f-0493-4b70-98ba-98533de7710b"
geocode_url = "https://geocode-maps.yandex.ru/1.x/"

search_key = "dda3ddba-c9ea-4ead-9010-f43fbc15c6e3"
search_url = "https://search-maps.yandex.ru/v1/"


def search(
    geocode: str,
    ll: tuple[float, float],
    spn: tuple[float, float],
) -> dict | None:
    response = requests.get(
        geocode_url,
        params=dict(
            apikey=geocode_key,
            geocode=geocode,
            format="json",
            ll=f"{ll[0]},{ll[1]}",
            spn=f"{spn[0]},{spn[1]}",
        ),
    )
    if response.status_code != 200:
        return None

    features = response.json()["response"]["GeoObjectCollection"]["featureMember"]
    if len(features) == 0:
        return None

    return features[0]["GeoObject"]


class MainWindow(QtWidgets.QMainWindow):
    ui: Ui_MainWindow

    center: tuple[float, float]
    point: tuple[float, float] | None
    address: str | None
    index: int | None

    def __init__(self) -> None:
        super().__init__()

        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)

        self.center = (127.514956, 50.260180)
        self.point = None
        self.address = None
        self.index = None

        self._update_map()

        self.ui.zoomSlider.valueChanged.connect(self._update_map)
        self.ui.layerSelector.currentIndexChanged.connect(self._update_map)
        self.ui.setButton.clicked.connect(self._search_button)
        self.ui.removeButton.clicked.connect(self.remove_button)
        self.ui.showIndexButton.toggled.connect(self.show_index)

    def get_spn(self) -> tuple[float, float]:
        z = self.ui.zoomSlider.value()
        return 180 / 2**z, 90 / 2**z

    def mousePressEvent(self, event: QtGui.QMouseEvent) -> None:
        def _search_obj() -> None:
            geo = search(
                f"{self.center[0]},{self.center[1]}",
                self.center,
                self.get_spn(),
            )
            if geo is None:
                self.ui.searchAddress.setText("Search error")
                self.update_map()
                return

            address = geo["metaDataProperty"]["GeocoderMetaData"]["Address"]
            lon, lat = map(float, geo["Point"]["pos"].split())
            self.point = (lon, lat)
            self.ui.removeButton.setEnabled(True)

            self.address = address["formatted"]
            self.index = address.get("postal_code", None)
            self.show_index()
            if self.index is not None:
                self.ui.showIndexButton.setEnabled(True)
            self.update_map()

        def _search_org() -> None:
            ll = self.center
            spn = self.get_spn()

            response = requests.get(
                search_url,
                dict(
                    apikey=search_key,
                    text=f"{ll[1]},{ll[0]}",
                    lang="ru_RU",
                    type="biz",
                ),
            )

            if response.status_code != 200:
                self.ui.searchAddress.setText("Search error")
                self.update_map()
                return

            features = response.json()["features"]
            if len(features) == 0:
                self.ui.searchAddress.setText("Organization not found")
                self.update_map()
                return

            geo = features[0]

            (lon1, lat1, lon2, lat2) = map(
                radians,
                (*ll, *geo["geometry"]["coordinates"]),
            )
            a = (
                sin((lat2 - lat1) / 2) ** 2
                + cos(lat1) * cos(lat2) * sin((lon2 - lon1) / 2) ** 2
            )
            length = R * 2 * atan2(sqrt(a), sqrt(1 - a))
            if length > 50:
                self.ui.searchAddress.setText("Organization not found")
                self.update_map()
                return

            self.point = geo["geometry"]["coordinates"]
            self.ui.removeButton.setEnabled(True)

            self.address = geo["properties"]["CompanyMetaData"]["address"]
            self.index = None
            self.show_index()
            if self.index is not None:
                self.ui.showIndexButton.setEnabled(True)
            self.update_map()

        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            self.ui.map.clear()
            self.ui.map.setText("Map is loading")
            self.ui.searchAddress.setText("Finding object")
            QtCore.QThreadPool.globalInstance().start(_search_obj)
        elif event.button() == QtCore.Qt.MouseButton.RightButton:
            self.ui.map.clear()
            self.ui.map.setText("Map is loading")
            self.ui.searchAddress.setText("Finding object")
            QtCore.QThreadPool.globalInstance().start(_search_org)
        return super().mousePressEvent(event)

    def keyPressEvent(self, event: QtGui.QKeyEvent) -> None:
        match event.key():
            # Zoom
            case QtCore.Qt.Key.Key_PageUp:
                self.ui.zoomSlider.setValue(self.ui.zoomSlider.value() + 1)
            case QtCore.Qt.Key.Key_PageDown:
                self.ui.zoomSlider.setValue(self.ui.zoomSlider.value() - 1)
            # Center
            case QtCore.Qt.Key.Key_Up:
                self.center = (self.center[0], self.center[1] + self.get_spn()[1])
                self._update_map()
            case QtCore.Qt.Key.Key_Down:
                self.center = (self.center[0], self.center[1] - self.get_spn()[1])
                self._update_map()
            case QtCore.Qt.Key.Key_Left:
                self.center = (self.center[0] - self.get_spn()[0], self.center[1])
                self._update_map()
            case QtCore.Qt.Key.Key_Right:
                self.center = (self.center[0] + self.get_spn()[0], self.center[1])
                self._update_map()
        return super().keyPressEvent(event)

    def search_button(self) -> None:
        geo = search(self.ui.searchField.text(), self.center, self.get_spn())
        if geo is None:
            self.ui.searchAddress.setText("Search error")
            self.update_map()
            return

        address = geo["metaDataProperty"]["GeocoderMetaData"]["Address"]
        lon, lat = map(float, geo["Point"]["pos"].split())
        self.point = (lon, lat)
        self.center = self.point
        self.ui.removeButton.setEnabled(True)

        self.address = address["formatted"]
        self.index = address.get("postal_code", None)
        self.show_index()
        if self.index is not None:
            self.ui.showIndexButton.setEnabled(True)
        self.update_map()

    def remove_button(self) -> None:
        self.point = None
        self.address = None
        self.index = None
        self.ui.showIndexButton.setEnabled(False)
        self.ui.removeButton.setEnabled(False)
        self.ui.showIndexButton.setChecked(False)
        self.ui.searchAddress.clear()
        self._update_map()

    def show_index(self) -> None:
        if self.ui.showIndexButton.isChecked():
            self.ui.searchAddress.setText(f"{self.address} [{self.index}]")
        else:
            self.ui.searchAddress.setText(self.address)

    def update_map(self) -> None:
        ll = self.center
        spn = self.get_spn()
        pt = self.point

        params = dict(
            apikey=static_key,
            size="650,450",
            l=["map", "sat", "sat,skl"][self.ui.layerSelector.currentIndex()],
            ll=f"{ll[0]},{ll[1]}",
            spn=f"{spn[0]},{spn[1]}",
        )

        if pt is not None:
            params["pt"] = f"{pt[0]},{pt[1]},org"

        response = requests.get(static_url, params)
        if response.status_code == 200:
            image = QtGui.QPixmap()
            image.loadFromData(response.content)
            self.ui.map.setPixmap(image)
        else:
            self.ui.map.setText("Map loading error")

    def _search_button(self) -> None:
        self.ui.map.clear()
        self.ui.map.setText("Map is loading")
        self.ui.searchAddress.setText("Finding object")
        QtCore.QThreadPool.globalInstance().start(self.search_button)

    def _update_map(self) -> None:
        self.ui.map.clear()
        self.ui.map.setText("Map is loading")
        QtCore.QThreadPool.globalInstance().start(self.update_map)


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    main = MainWindow()
    main.show()
    app.exec()
