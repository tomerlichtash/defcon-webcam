/* Stars Outside — MapManager (standalone Leaflet integration) */
import { store, selectSiteName, selectDefconLabel } from "./store.js";

export class MapManager {
  constructor() {
    this.leafletMap = null;
    this.mapMarkers = [];
    this.userLocation = null;
    this.userCircle = null;
    this.userMarker = null;
    this._alertMarkers = new Map(); /* key → L.circleMarker */
    this._tileLayer = null;
    this._initialFitDone = false;
    this._lastLevel = store.getState().defcon.level;
    this._lastCityCount = 0;
    this._locateRetries = 0;

    /* React to store changes */
    store.subscribe(() => this._onStoreChange());
  }

  _onStoreChange() {
    const state = store.getState();
    const level = state.defcon.level;
    const cities = state.defcon.alertCities;
    const theme = state.ui.theme;

    const levelChanged = level !== this._lastLevel;

    /* Defcon level change → update marker colors */
    if (levelChanged) {
      this._updateColors(level);
      this._lastLevel = level;
    }

    /* Alert cities → sync markers (on city change OR level change) */
    if (cities.length !== this._lastCityCount || levelChanged) {
      this._syncAlertCities(level, cities);
      this._lastCityCount = cities.length;
    }

    /* Theme change → swap tiles */
    if (theme !== this._lastTheme && this.leafletMap && this._tileLayer) {
      this._swapTiles(theme);
      this._lastTheme = theme;
    }

    /* Update page title */
    document.title = `${selectSiteName(state)} - ${selectDefconLabel(state)}`;
  }

  initMap() {
    if (this.leafletMap) return;
    const mapEl = document.getElementById("leaflet-map");
    if (!mapEl) return;

    /* Guard against Leaflet tooltip/marker crash when _map is null */
    for (const Proto of [
      L.Tooltip.prototype,
      L.Marker.prototype,
      L.CircleMarker.prototype,
    ]) {
      if (Proto._updatePosition) {
        const orig = Proto._updatePosition;
        Proto._updatePosition = function () {
          if (!this._map) return;
          orig.apply(this, arguments);
        };
      }
      if (Proto._animateZoom) {
        const orig = Proto._animateZoom;
        Proto._animateZoom = function () {
          if (!this._map) return;
          orig.apply(this, arguments);
        };
      }
    }

    const map = L.map("leaflet-map", {
      zoomControl: false,
      attributionControl: false,
      zoomAnimation: true,
      markerZoomAnimation: true,
    }).fitBounds([
      [29.557, 34.2],
      [33.28, 36.0],
    ]);

    L.control.zoom({ position: "topright" }).addTo(map);

    const darkMode = store.getState().ui.theme === "dark";
    const tileUrl = darkMode
      ? "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
      : "https://{s}.basemaps.cartocdn.com/rastertiles/voyager_labels_under/{z}/{x}/{y}{r}.png";
    this._tileLayer = L.tileLayer(tileUrl, {
      maxZoom: 18,
      keepBuffer: 4,
      loadBuffer: 2,
      updateWhenZooming: false,
      updateWhenIdle: true,
    }).addTo(map);
    this._lastTheme = store.getState().ui.theme;

    /* Recenter button */
    const self = this;
    const RecenterControl = L.Control.extend({
      options: { position: "topright" },
      onAdd: () => {
        const div = L.DomUtil.create("div", "leaflet-control-recenter");
        div.title = "Re-center";
        div.innerHTML =
          '<svg viewBox="0 0 24 24" fill="none" stroke="#333" stroke-width="2"><circle cx="12" cy="12" r="3"/><line x1="12" y1="2" x2="12" y2="6"/><line x1="12" y1="18" x2="12" y2="22"/><line x1="2" y1="12" x2="6" y2="12"/><line x1="18" y1="12" x2="22" y2="12"/></svg>';
        L.DomEvent.disableClickPropagation(div);
        div.addEventListener("click", () => self.recenterMap());
        return div;
      },
    });
    new RecenterControl().addTo(map);

    this.leafletMap = map;
    setTimeout(() => map.invalidateSize(), 200);

    /* Place pre-loaded city markers */
    this.mapCities = window.__mapCities || [];
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
      this.mapMarkers.push({ city, marker, el });
    });
  }

  locateUser() {
    if (!navigator.geolocation) return;
    if (!this.leafletMap) {
      if (this._locateRetries++ < 10) setTimeout(() => this.locateUser(), 500);
      return;
    }
    this._locateRetries = 0;
    navigator.geolocation.getCurrentPosition(
      (pos) => this._placeUser(pos.coords.latitude, pos.coords.longitude),
      () => this._placeUser(32.072, 34.81),
      { enableHighAccuracy: false, timeout: 15000, maximumAge: 300000 },
    );
  }

  _placeUser(lat, lng) {
    this.userLocation = [lat, lng];
    if (this.userCircle) {
      this.userCircle.setLatLng([lat, lng]);
      this.userMarker.setLatLng([lat, lng]);
    } else {
      const level = store.getState().defcon.level;
      const color =
        level === 2 ? "#ff0000" : level === 4 ? "#00cc00" : "#4488ff";
      this.userCircle = L.circle([lat, lng], {
        radius: 2500,
        color,
        fillColor: color,
        fillOpacity: 0.18,
        weight: 2,
        dashArray: "6,4",
      }).addTo(this.leafletMap);
      this.userMarker = L.circleMarker([lat, lng], {
        radius: 6,
        color: "#fff",
        weight: 2,
        fillColor: color,
        fillOpacity: 1,
      }).addTo(this.leafletMap);
      const strings = store.getState().ui.strings;
      this.userMarker.bindTooltip(strings.you_are_here || "You are here", {
        permanent: true,
        direction: "right",
        offset: [10, 0],
        className: "user-tooltip",
      });
      this._updateColors(level);
      this.initialFit();
    }
  }

  _updateColors(level) {
    if (!this.userCircle || !this.userMarker) return;
    const colors = { 2: "#ff0000", 4: "#00cc00", 5: "#4488ff" };
    const color = colors[level] || "#4488ff";
    this.userCircle.setStyle({ color, fillColor: color });
    this.userMarker.setStyle({ fillColor: color });
  }

  _swapTiles(theme) {
    if (!this.leafletMap || !this._tileLayer) return;
    this.leafletMap.removeLayer(this._tileLayer);
    const tileUrl =
      theme === "dark"
        ? "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
        : "https://{s}.basemaps.cartocdn.com/rastertiles/voyager_labels_under/{z}/{x}/{y}{r}.png";
    this._tileLayer = L.tileLayer(tileUrl, {
      maxZoom: 18,
      keepBuffer: 4,
      loadBuffer: 2,
      updateWhenZooming: false,
      updateWhenIdle: true,
    }).addTo(this.leafletMap);
  }

  _syncAlertCities(level, cities) {
    if (level === 5 || cities.length === 0) {
      this._clearAlertMarkers();
      return;
    }
    if (level !== 2) return;
    const newKeys = new Set(cities.map((c) => `${c.name}|${c.lat}|${c.lng}`));

    /* Remove markers no longer in list */
    for (const [key, marker] of this._alertMarkers) {
      if (!newKeys.has(key)) {
        if (marker.getTooltip()) marker.unbindTooltip();
        this.leafletMap.removeLayer(marker);
        this._alertMarkers.delete(key);
      }
    }

    /* Add new markers */
    let added = false;
    for (const city of cities) {
      const key = `${city.name}|${city.lat}|${city.lng}`;
      if (!this._alertMarkers.has(key) && this.leafletMap) {
        const marker = L.circleMarker([city.lat, city.lng], {
          radius: 4,
          color: "var(--so-color-red)",
          weight: 1,
          fillColor: "var(--so-color-red)",
          fillOpacity: 0.7,
        }).addTo(this.leafletMap);
        marker.bindTooltip(city.name_he || city.name, {
          direction: "right",
          offset: [6, 0],
          className: "city-tooltip defcon2",
        });
        this._alertMarkers.set(key, marker);
        added = true;
      }
    }
    if (added) this.initialFit();
  }

  _clearAlertMarkers() {
    if (!this.leafletMap) return;
    for (const [, marker] of this._alertMarkers) {
      if (marker.getTooltip()) marker.unbindTooltip();
      this.leafletMap.removeLayer(marker);
    }
    this._alertMarkers.clear();
  }

  recenterMap() {
    if (!this.leafletMap) return;
    if (this.userLocation && this.userCircle) {
      this.leafletMap.fitBounds(this.userCircle.getBounds(), {
        padding: [30, 30],
      });
    } else if (this._alertMarkers.size > 0) {
      const latlngs = [...this._alertMarkers.values()].map((m) =>
        m.getLatLng(),
      );
      this.leafletMap.fitBounds(L.latLngBounds(latlngs), { padding: [30, 30] });
    } else {
      this.leafletMap.setView([31.5, 34.8], 8);
    }
  }

  initialFit() {
    if (this._initialFitDone || !this.leafletMap) return;
    this._initialFitDone = true;
    const bounds = L.latLngBounds([
      [29.557, 34.2],
      [33.28, 36.0],
    ]);
    if (this.userCircle) bounds.extend(this.userCircle.getBounds());
    else if (this.userLocation) bounds.extend(L.latLng(this.userLocation));
    for (const marker of this._alertMarkers.values())
      bounds.extend(marker.getLatLng());
    this.leafletMap.fitBounds(bounds, { padding: [20, 20] });
  }
}
