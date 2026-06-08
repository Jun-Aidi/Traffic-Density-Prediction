import { useState, useEffect } from 'react';
import { BarChart3 } from 'lucide-react';

export default function TrafficChart() {
  const [hourlyData, setHourlyData] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchHistory = async () => {
      try {
        const res = await fetch('/api/traffic/history');
        const data = await res.json();
        setHourlyData(data);
      } catch (error) {
        console.error("Error fetching history:", error);
      } finally {
        setLoading(false);
      }
    };

    fetchHistory();
    // Update every 5 minutes
    const interval = setInterval(fetchHistory, 300000);
    return () => clearInterval(interval);
  }, []);

  if (loading) {
    return (
      <div className="glass-panel chart-widget" style={{ display: 'flex', justifyContent: 'center', alignItems: 'center' }}>
        Loading Chart Data...
      </div>
    );
  }

  return (
    <div className="glass-panel chart-widget">
      <div className="widget-header">
        <BarChart3 size={20} color="var(--accent-orange)" />
        <h3>Pola Kemacetan Harian (Rata-rata)</h3>
      </div>
      
      <div className="mock-chart">
        {hourlyData.map((data, idx) => (
          <div className="bar-wrapper" key={idx}>
            <div 
              className={`bar ${data.high ? 'high' : ''} ${data.hour === '10' ? 'active' : ''}`} 
              style={{ height: `${data.value}%` }}
              title={`Jam ${data.hour}:00`}
            ></div>
            <span className="bar-label">{data.hour}</span>
          </div>
        ))}
      </div>
      
      <div style={{ marginTop: '36px', fontSize: '0.85rem', color: 'var(--text-muted)', display: 'flex', justifyContent: 'space-between' }}>
        <span>Tinggi grafik = Tingkat Kepadatan</span>
        <div style={{ display: 'flex', gap: '12px' }}>
          <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
            <span style={{ width: '8px', height: '8px', background: 'var(--primary-neon)', borderRadius: '50%' }}></span> Saat Ini
          </span>
          <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
            <span style={{ width: '8px', height: '8px', background: 'var(--accent-red)', borderRadius: '50%' }}></span> Jam Sibuk
          </span>
        </div>
      </div>
    </div>
  );
}
