/* Map module — Leaflet initialization, user location, markers */
var MapModule = {
  state: {
    leafletMap: null,
    mapMarkers: [],
    userLocation: null,
    userCircle: null,
    userMarker: null,
    alertCityMarkers: [],
    mapCities: [],
    _alertCityKeys: {},
    _initialFitDone: false,
  },

  initMap() {
    if (this.leafletMap) return;
    const mapEl = document.getElementById("leaflet-map");
    if (!mapEl) return;
    const map = L.map("leaflet-map", {
      zoomControl: false,
      attributionControl: false,
    }).fitBounds([
      [29.557, 34.2],
      [33.28, 36.0],
    ]);
    L.control.zoom({ position: "topright" }).addTo(map);
    const tileUrl = this.darkMode
      ? "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
      : "https://{s}.basemaps.cartocdn.com/rastertiles/voyager_labels_under/{z}/{x}/{y}{r}.png";
    this._tileLayer = L.tileLayer(tileUrl, {
      maxZoom: 18,
      keepBuffer: 4,
      loadBuffer: 2,
      updateWhenZooming: false,
      updateWhenIdle: true,
    }).addTo(map);

    /* Recenter button */
    const RecenterControl = L.Control.extend({
      options: { position: "topright" },
      onAdd: () => {
        const div = L.DomUtil.create("div", "leaflet-control-recenter");
        div.title = "Re-center";
        div.innerHTML =
          '<svg viewBox="0 0 24 24" fill="none" stroke="#333" stroke-width="2"><circle cx="12" cy="12" r="3"/><line x1="12" y1="2" x2="12" y2="6"/><line x1="12" y1="18" x2="12" y2="22"/><line x1="2" y1="12" x2="6" y2="12"/><line x1="18" y1="12" x2="22" y2="12"/></svg>';
        L.DomEvent.disableClickPropagation(div);
        div.addEventListener("click", () => {
          this.recenterMap();
        });
        return div;
      },
    });
    new RecenterControl().addTo(map);

    this.leafletMap = map;
    setTimeout(() => {
      map.invalidateSize();
    }, 200);

    this.mapCities.forEach((city) => {
      const el = document.createElement("div");
      el.className = "alert-marker";
      const marker = L.marker([city.lat, city.lng], {
        icon: L.divIcon({
          className: "",
          html: el,
          iconSize: [14, 14],
          iconAnchor: [7, 7],
        }),
      }).addTo(map);
      marker.bindTooltip(city.label, {
        permanent: city.watched,
        direction: "right",
        offset: [10, 0],
        className: "city-tooltip",
      });
      this.mapMarkers.push({ city: city, marker: marker, el: el });
    });
  },

  _locateRetries: 0,
  locateUser() {
    if (!navigator.geolocation) return;
    if (!this.leafletMap) {
      if (this._locateRetries++ < 10) {
        setTimeout(() => {
          this.locateUser();
        }, 500);
      }
      return;
    }
    this._locateRetries = 0;
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        this._placeUser(pos.coords.latitude, pos.coords.longitude);
      },
      () => {
        this._placeUser(32.072, 34.81);
      },
      { enableHighAccuracy: false, timeout: 15000, maximumAge: 300000 },
    );
  },

  _placeUser(lat, lng) {
    this.userLocation = [lat, lng];
    if (this.userCircle) {
      this.userCircle.setLatLng([lat, lng]);
      this.userMarker.setLatLng([lat, lng]);
    } else {
      const defconColor =
        this.defcon === 2
          ? "#ff0000"
          : this.defcon === 4
            ? "#00cc00"
            : "#4488ff";
      this.userCircle = L.circle([lat, lng], {
        radius: 2500,
        color: defconColor,
        fillColor: defconColor,
        fillOpacity: 0.18,
        weight: 2,
        dashArray: "6,4",
      }).addTo(this.leafletMap);
      this.userMarker = L.circleMarker([lat, lng], {
        radius: 6,
        color: "#fff",
        weight: 2,
        fillColor: defconColor,
        fillOpacity: 1,
      }).addTo(this.leafletMap);
      this.userMarker.bindTooltip(this.t("you_are_here"), {
        permanent: true,
        direction: "right",
        offset: [10, 0],
        className: "user-tooltip",
      });
      this.updateMapMarkers();
      this.initialFit();
    }
  },

  recenterMap() {
    if (!this.leafletMap) return;
    if (this.userLocation && this.userCircle) {
      this.leafletMap.flyToBounds(this.userCircle.getBounds(), {
        padding: [30, 30],
        duration: 1,
      });
    } else if (this.alertCityMarkers.length > 0) {
      const bounds = L.latLngBounds(
        this.alertCityMarkers.map((m) => m.getLatLng()),
      );
      this.leafletMap.flyToBounds(bounds, { padding: [30, 30], duration: 1 });
    } else {
      this.leafletMap.flyTo([31.5, 34.8], 8, { duration: 1 });
    }
  },

  initialFit() {
    if (this._initialFitDone || !this.leafletMap) return;
    this._initialFitDone = true;
    /* Always show full Israel: Eilat to Metula */
    const bounds = L.latLngBounds([
      [29.557, 34.2],
      [33.28, 36.0],
    ]);
    if (this.userCircle) {
      bounds.extend(this.userCircle.getBounds());
    } else if (this.userLocation) {
      bounds.extend(L.latLng(this.userLocation));
    }
    this.alertCityMarkers.forEach((m) => {
      bounds.extend(m.getLatLng());
    });
    if (bounds) {
      this.leafletMap.fitBounds(bounds, { padding: [20, 20] });
    }
  },

  clearAlertCities() {
    if (!this.leafletMap) return;
    this.alertCityMarkers.forEach((m) => {
      this.leafletMap.removeLayer(m);
    });
    this.alertCityMarkers = [];
    this._alertCityKeys = {};
  },

  updateMapMarkers() {
    if (!this.userCircle || !this.userMarker) return;
    const colors = { 2: "#ff0000", 4: "#00cc00", 5: "#4488ff" };
    const color = colors[this.defcon] || "#4488ff";
    this.userCircle.setStyle({ color: color, fillColor: color });
    this.userMarker.setStyle({ fillColor: color });
  },
};
