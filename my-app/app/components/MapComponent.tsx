'use client';

import { useEffect, useRef } from 'react';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';

interface Waypoint {
  id: string;
  lat: number;
  lng: number;
  order: number;
}

interface MapComponentProps {
  waypoints: Waypoint[];
  onMapClick: (lat: number, lng: number) => void;
  onWaypointRemove: (id: string) => void;
}

export default function MapComponent({ waypoints, onMapClick, onWaypointRemove }: MapComponentProps) {
  const mapRef = useRef<L.Map | null>(null);
  const mapContainerRef = useRef<HTMLDivElement>(null);
  const markersRef = useRef<{ [key: string]: L.Marker }>({});
  const polylineRef = useRef<L.Polyline | null>(null);
  const arrowsRef = useRef<L.Polyline[]>([]);

  // Initialize map
  useEffect(() => {
    if (!mapContainerRef.current || mapRef.current) return;

    const map = L.map(mapContainerRef.current, {
      center: [42.36, -71.06], //map center
      zoom: 13,
      zoomControl: true
    });

    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
    }).addTo(map);

    map.on('click', (e) => {
      onMapClick(e.latlng.lat, e.latlng.lng);
    });

    mapRef.current = map;

    return () => {
      map.remove();
      mapRef.current = null;
    };
  }, []);

  const calculateDistance = (lat1: number, lng1: number, lat2: number, lng2: number) => {
    const R = 6371e3; // Earth's radius in meters
    const φ1 = lat1 * Math.PI / 180;
    const φ2 = lat2 * Math.PI / 180;
    const Δφ = (lat2 - lat1) * Math.PI / 180;
    const Δλ = (lng2 - lng1) * Math.PI / 180;

    const a = Math.sin(Δφ / 2) * Math.sin(Δφ / 2) +
              Math.cos(φ1) * Math.cos(φ2) *
              Math.sin(Δλ / 2) * Math.sin(Δλ / 2);
    const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));

    return R * c;
  };

  useEffect(() => {
    if (!mapRef.current) return;

    const map = mapRef.current;

    // Remove old markers
    Object.values(markersRef.current).forEach(marker => {
      map.removeLayer(marker);
    });
    markersRef.current = {};

    // Remove old polyline
    if (polylineRef.current) {
      map.removeLayer(polylineRef.current);
      polylineRef.current = null;
    }

    // Remove old arrows
    arrowsRef.current.forEach(arrow => {
      map.removeLayer(arrow);
    });
    arrowsRef.current = [];

    // Add new markers
    waypoints.forEach((wp, index) => {
      let markerColor = '#3b82f6'; // Blue
      if (index === 0 && waypoints.length > 1) {
        markerColor = '#10b981'; // Green for start
      } else if (index === waypoints.length - 1 && waypoints.length > 1) {
        markerColor = '#ef4444'; // Red for end
      }

      const icon = L.divIcon({
        className: 'custom-waypoint-marker',
        html: `
          <div style="
            width: 40px;
            height: 40px;
            background: ${markerColor};
            border: 3px solid white;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: bold;
            color: white;
            font-size: 16px;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
            cursor: pointer;
            transition: transform 0.2s;
          ">
            ${wp.order}
          </div>
        `,
        iconSize: [40, 40],
        iconAnchor: [20, 20]
      });

      // Calculate distance to next waypoint if exists
      let distanceText = '';
      if (index < waypoints.length - 1) {
        const nextWp = waypoints[index + 1];
        const distance = calculateDistance(wp.lat, wp.lng, nextWp.lat, nextWp.lng);
        if (distance < 1000) {
          distanceText = `<div style="margin-top: 4px; font-size: 11px; color: #64748b;">
            Next: ${Math.round(distance)}m
          </div>`;
        } else {
          distanceText = `<div style="margin-top: 4px; font-size: 11px; color: #64748b;">
            Next: ${(distance / 1000).toFixed(2)}km
          </div>`;
        }
      }

      const marker = L.marker([wp.lat, wp.lng], { icon })
        .addTo(map)
        .bindPopup(`
          <div style="font-family: system-ui, sans-serif; padding: 4px; min-width: 150px;">
            <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 8px;">
              <div style="
                width: 24px;
                height: 24px;
                background: ${markerColor};
                border-radius: 50%;
                display: flex;
                align-items: center;
                justify-content: center;
                color: white;
                font-weight: bold;
                font-size: 12px;
              ">${wp.order}</div>
              <strong style="color: #1e293b; font-size: 14px;">
                ${index === 0 && waypoints.length > 1 ? 'Start Point' : 
                  index === waypoints.length - 1 && waypoints.length > 1 ? 'End Point' : 
                  `Waypoint ${wp.order}`}
              </strong>
            </div>
            <div style="margin-top: 4px; font-size: 12px; color: #64748b; font-family: monospace;">
              <div>Lat: ${wp.lat.toFixed(6)}</div>
              <div>Lng: ${wp.lng.toFixed(6)}</div>
            </div>
            ${distanceText}
            <button 
              onclick="window.removeWaypoint('${wp.id}')"
              style="
                margin-top: 8px;
                width: 100%;
                background: #ef4444;
                color: white;
                border: none;
                padding: 6px 12px;
                border-radius: 6px;
                font-size: 12px;
                font-weight: 600;
                cursor: pointer;
              "
              onmouseover="this.style.background='#dc2626'"
              onmouseout="this.style.background='#ef4444'"
            >
              Remove Waypoint
            </button>
          </div>
        `);

      markersRef.current[wp.id] = marker;
    });

    if (waypoints.length > 1) {
      const coordinates = waypoints.map(wp => [wp.lat, wp.lng] as [number, number]);
      
      polylineRef.current = L.polyline(coordinates, {
        color: '#3b82f6',
        weight: 4,
        opacity: 0.8,
        lineJoin: 'round',
        lineCap: 'round'
      }).addTo(map);

      for (let i = 0; i < coordinates.length - 1; i++) {
        const start = coordinates[i];
        const end = coordinates[i + 1];
        
        const midLat = (start[0] + end[0]) / 2;
        const midLng = (start[1] + end[1]) / 2;
        
        const angle = Math.atan2(end[1] - start[1], end[0] - start[0]) * 180 / Math.PI;
        
        const arrowIcon = L.divIcon({
          className: 'route-arrow',
          html: `
            <div style="
              width: 0;
              height: 0;
              border-left: 8px solid transparent;
              border-right: 8px solid transparent;
              border-bottom: 12px solid #3b82f6;
              transform: rotate(${angle + 90}deg);
              filter: drop-shadow(0 2px 4px rgba(0, 0, 0, 0.2));
            "></div>
          `,
          iconSize: [16, 16],
          iconAnchor: [8, 8]
        });
        
        const arrowMarker = L.marker([midLat, midLng], { 
          icon: arrowIcon,
          interactive: false
        }).addTo(map);
        
        arrowsRef.current.push(arrowMarker as any);
      }

      // Fit map to show all waypoints
      const bounds = L.latLngBounds(coordinates);
      map.fitBounds(bounds, { padding: [50, 50] });
    }

    (window as any).removeWaypoint = onWaypointRemove;

    return () => {
      delete (window as any).removeWaypoint;
    };
  }, [waypoints, onWaypointRemove]);

  return (
    <div ref={mapContainerRef} className="w-full h-full" />
  );
}