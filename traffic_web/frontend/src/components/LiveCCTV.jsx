import { useState, useEffect } from 'react';
import { Video, Clock, Activity } from 'lucide-react';
import ReactPlayer from 'react-player';

export default function LiveCCTV() {
  const [current, setCurrent] = useState(null);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const res = await fetch('/api/traffic/current');
        const data = await res.json();
        setCurrent(data);
      } catch (error) {
        console.error("Error fetching data:", error);
      }
    };

    fetchData();
    // Update every 10 seconds
    const interval = setInterval(fetchData, 10000);
    return () => clearInterval(interval);
  }, []);

  const neonColor = current?.status_en === 'High' ? 'var(--accent-red)' : 
                   current?.status_en === 'Medium' ? 'var(--accent-orange)' : 'var(--primary-neon)';

  return (
    <div className="glass-panel cctv-container">
      <div className="cctv-header">
        <h2><Video size={24} color="var(--primary-neon)" /> Live Traffic Feed</h2>
        <div className="live-badge">
          <div className="live-dot"></div>
          LIVE
        </div>
      </div>
      
      <div className="video-wrapper">
        <iframe
          src="/api/cctv"
          width="100%"
          height="100%"
          style={{ border: 'none', overflow: 'hidden', borderRadius: '12px' }}
          allowFullScreen
          title="CCTV Feed"
        />
      </div>
      
      <div className="camera-info">
        <div className="info-item">
          <span className="info-label">Lokasi</span>
          <span className="info-value">{current?.location || "Gelora 0-17"}</span>
        </div>
        <div className="info-item">
          <span className="info-label">Status Kemacetan</span>
          <span className="info-value" style={{ color: neonColor }}>
            {current ? `${current.status_id} (${current.status_en})` : 'Loading...'}
          </span>
        </div>
        <div className="info-item">
          <span className="info-label">Update Terakhir</span>
          <span className="info-value">{current?.last_update || "Memuat..."}</span>
        </div>
      </div>
    </div>
  );
}
