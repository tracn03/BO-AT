'use client';

import { useState } from 'react';
import dynamic from 'next/dynamic';
import { Play, Navigation, Battery, Wind, Gauge, Thermometer } from 'lucide-react';

// Dynamically import the map component to avoid SSR issues
const MapComponent = dynamic(() => import('./components/MapComponent'), {
  ssr: false,
  loading: () => (
    <div className="w-full h-full flex items-center justify-center bg-slate-100">
      <div className="text-slate-400">Loading map...</div>
    </div>
  )
});

interface Waypoint {
  id: string;
  lat: number;
  lng: number;
  order: number;
}

interface Metrics {
  battery: number;
  windSpeed: number;
  speed: number;
  temperature: number;
}

export default function MissionPlanner() {
  const [waypoints, setWaypoints] = useState<Waypoint[]>([]);
  const [status, setStatus] = useState<'idle' | 'running' | 'completed'>('idle');
  const [metrics, setMetrics] = useState<Metrics>({
    battery: 85,
    windSpeed: 12,
    speed: 0,
    temperature: 72
  });

  const handleMapClick = (lat: number, lng: number) => {
    setWaypoints(prevWaypoints => {
      const newWaypoint: Waypoint = {
        id: `wp-${Date.now()}`,
        lat,
        lng,
        order: prevWaypoints.length + 1
      };
      console.log('Added waypoint:', newWaypoint);
      console.log('Total waypoints:', prevWaypoints.length + 1);
      return [...prevWaypoints, newWaypoint];
    });
  };

  const handleStartMission = () => {
    if (waypoints.length > 0) {
      setStatus('running');
      // Simulate mission running with changing metrics
      const interval = setInterval(() => {
        setMetrics(prev => ({
          battery: Math.max(0, prev.battery - 0.5),
          windSpeed: Math.max(0, prev.windSpeed + (Math.random() - 0.5) * 2),
          speed: Math.min(25, Math.max(0, prev.speed + (Math.random() - 0.3) * 3)),
          temperature: prev.temperature + (Math.random() - 0.5) * 0.5
        }));
      }, 1000);

      return () => clearInterval(interval);
    }
  };

  const handleReset = () => {
    setWaypoints([]);
    setStatus('idle');
    setMetrics({
      battery: 85,
      windSpeed: 12,
      speed: 0,
      temperature: 72
    });
    console.log('Reset all waypoints');
  };

  const removeWaypoint = (id: string) => {
    setWaypoints(prevWaypoints => {
      const filtered = prevWaypoints.filter(wp => wp.id !== id);
      const reordered = filtered.map((wp, index) => ({
        ...wp,
        order: index + 1
      }));
      console.log('Removed waypoint:', id);
      console.log('Remaining waypoints:', reordered.length);
      return reordered;
    });
  };

  return (
    <div className="h-screen w-screen flex flex-col bg-slate-50">
      {/* Header */}
      <header className="bg-white border-b border-slate-200 px-6 py-4 shadow-sm">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 bg-gradient-to-br from-blue-500 to-blue-600 rounded-xl flex items-center justify-center shadow-lg shadow-blue-500/20">
            <Navigation className="w-5 h-5 text-white" />
          </div>
          <h1 className="text-2xl font-bold text-slate-800 tracking-tight">
            BO-AT Mission Planner
          </h1>
        </div>
      </header>

      {/* Main Content */}
      <div className="flex-1 flex overflow-hidden">
        {/* Map Section */}
        <div className="flex-1 relative">
          <MapComponent 
            waypoints={waypoints}
            onMapClick={handleMapClick}
            onWaypointRemove={removeWaypoint}
          />
        </div>

        {/* Control Panel */}
        <div className="w-96 bg-white border-l border-slate-200 flex flex-col overflow-hidden">
          <div className="flex-1 overflow-y-auto p-6 space-y-6">
            {/* Mission Control */}
            <div>
              <h2 className="text-xl font-bold text-slate-800 mb-4">Mission Control</h2>
              
              <button
                onClick={handleStartMission}
                disabled={waypoints.length === 0 || status === 'running'}
                className="w-full bg-gradient-to-r from-emerald-500 to-emerald-600 hover:from-emerald-600 hover:to-emerald-700 disabled:from-slate-300 disabled:to-slate-400 text-white font-semibold py-3 px-4 rounded-lg shadow-lg shadow-emerald-500/25 disabled:shadow-none transition-all duration-200 flex items-center justify-center gap-2 mb-4"
              >
                <Play className="w-5 h-5 fill-current" />
                Start Mission
              </button>

              <button
                onClick={handleReset}
                className="w-full bg-slate-100 hover:bg-slate-200 text-slate-700 font-medium py-2 px-4 rounded-lg transition-colors duration-200 flex items-center justify-center gap-2"
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                </svg>
                Reset
              </button>

              <div className="grid grid-cols-2 gap-4 mt-4">
                <div>
                  <div className="text-sm font-medium text-slate-600 mb-1">Status:</div>
                  <div className="flex items-center gap-2">
                    <span className={`w-2 h-2 rounded-full ${
                      status === 'idle' ? 'bg-slate-400' :
                      status === 'running' ? 'bg-emerald-500 animate-pulse' :
                      'bg-blue-500'
                    }`} />
                    <span className="text-sm font-semibold text-slate-700 capitalize">
                      {status}
                    </span>
                  </div>
                </div>
                <div>
                  <div className="text-sm font-medium text-slate-600 mb-1">Waypoints:</div>
                  <div className="text-2xl font-bold text-slate-800">
                    {waypoints.length}
                  </div>
                </div>
              </div>
            </div>

            {/* Waypoints List */}
            <div>
              <h3 className="text-lg font-bold text-slate-800 mb-3 flex items-center gap-2">
                <Navigation className="w-5 h-5 text-blue-500" />
                Waypoints
              </h3>
              
              {waypoints.length === 0 ? (
                <div className="text-center py-8 px-4 bg-slate-50 rounded-lg border border-dashed border-slate-300">
                  <p className="text-sm text-slate-500">
                    Click on the map to add waypoints
                  </p>
                </div>
              ) : (
                <div className="space-y-2 max-h-64 overflow-y-auto">
                  {waypoints.map((wp) => (
                    <div
                      key={wp.id}
                      className="bg-slate-50 hover:bg-slate-100 rounded-lg p-3 transition-colors duration-150 group"
                    >
                      <div className="flex items-start justify-between">
                        <div className="flex-1">
                          <div className="flex items-center gap-2 mb-1">
                            <span className={`w-6 h-6 rounded-full text-white text-xs font-bold flex items-center justify-center ${
                              wp.order === 1 && waypoints.length > 1 ? 'bg-emerald-500' :
                              wp.order === waypoints.length && waypoints.length > 1 ? 'bg-red-500' :
                              'bg-blue-500'
                            }`}>
                              {wp.order}
                            </span>
                            <span className="font-semibold text-slate-700 text-sm">
                              {wp.order === 1 && waypoints.length > 1 ? 'Start' :
                               wp.order === waypoints.length && waypoints.length > 1 ? 'End' :
                               `Waypoint ${wp.order}`}
                            </span>
                          </div>
                          <div className="text-xs text-slate-500 font-mono ml-8">
                            <div>Lat: {wp.lat.toFixed(6)}</div>
                            <div>Lng: {wp.lng.toFixed(6)}</div>
                          </div>
                        </div>
                        <button
                          onClick={() => removeWaypoint(wp.id)}
                          className="text-slate-400 hover:text-red-500 opacity-0 group-hover:opacity-100 transition-all duration-150"
                        >
                          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                          </svg>
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Metrics */}
            <div>
              <h3 className="text-lg font-bold text-slate-800 mb-3">Metrics</h3>
              
              <div className="grid grid-cols-2 gap-3">
                {/* Battery */}
                <div className="bg-gradient-to-br from-emerald-50 to-emerald-100 rounded-lg p-4 border border-emerald-200">
                  <div className="flex items-center gap-2 mb-2">
                    <Battery className="w-4 h-4 text-emerald-600" />
                    <span className="text-xs font-semibold text-emerald-700 uppercase tracking-wide">
                      Battery
                    </span>
                  </div>
                  <div className="text-3xl font-bold text-emerald-700">
                    {Math.round(metrics.battery)}%
                  </div>
                  <div className="mt-2 h-1.5 bg-emerald-200 rounded-full overflow-hidden">
                    <div 
                      className="h-full bg-emerald-500 transition-all duration-300"
                      style={{ width: `${metrics.battery}%` }}
                    />
                  </div>
                </div>

                {/* Wind Speed */}
                <div className="bg-gradient-to-br from-blue-50 to-blue-100 rounded-lg p-4 border border-blue-200">
                  <div className="flex items-center gap-2 mb-2">
                    <Wind className="w-4 h-4 text-blue-600" />
                    <span className="text-xs font-semibold text-blue-700 uppercase tracking-wide">
                      Wind Speed
                    </span>
                  </div>
                  <div className="text-3xl font-bold text-blue-700">
                    {metrics.windSpeed.toFixed(1)}
                    <span className="text-lg ml-1">kts</span>
                  </div>
                </div>

                {/* Speed */}
                <div className="bg-gradient-to-br from-purple-50 to-purple-100 rounded-lg p-4 border border-purple-200">
                  <div className="flex items-center gap-2 mb-2">
                    <Gauge className="w-4 h-4 text-purple-600" />
                    <span className="text-xs font-semibold text-purple-700 uppercase tracking-wide">
                      Speed
                    </span>
                  </div>
                  <div className="text-3xl font-bold text-purple-700">
                    {metrics.speed.toFixed(1)}
                    <span className="text-lg ml-1">kts</span>
                  </div>
                </div>

                {/* Temperature */}
                <div className="bg-gradient-to-br from-orange-50 to-orange-100 rounded-lg p-4 border border-orange-200">
                  <div className="flex items-center gap-2 mb-2">
                    <Thermometer className="w-4 h-4 text-orange-600" />
                    <span className="text-xs font-semibold text-orange-700 uppercase tracking-wide">
                      Temp
                    </span>
                  </div>
                  <div className="text-3xl font-bold text-orange-700">
                    {Math.round(metrics.temperature)}°
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}