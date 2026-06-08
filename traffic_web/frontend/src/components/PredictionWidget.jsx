import { useState, useEffect } from 'react';
import { BrainCircuit } from 'lucide-react';

export default function PredictionWidget() {
  const [current, setCurrent] = useState(null);
  const [prediction, setPrediction] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [currentRes, predRes] = await Promise.all([
          fetch('/api/traffic/current'),
          fetch('/api/traffic/prediction')
        ]);
        
        const currentData = await currentRes.json();
        const predData = await predRes.json();
        
        setCurrent(currentData);
        setPrediction(predData);
      } catch (error) {
        console.error("Error fetching data:", error);
      } finally {
        setLoading(false);
      }
    };

    fetchData();
    // Update every 10 seconds
    const interval = setInterval(fetchData, 10000);
    return () => clearInterval(interval);
  }, []);

  if (loading || !current || !prediction) {
    return (
      <div className="glass-panel prediction-widget" style={{ display: 'flex', justifyContent: 'center', alignItems: 'center' }}>
        Loading AI Prediction...
      </div>
    );
  }

  // Determine color based on status
  const neonColor = current.status_en === 'High' ? 'var(--accent-red)' : 
                   current.status_en === 'Medium' ? 'var(--accent-orange)' : 'var(--primary-neon)';

  return (
    <div className="glass-panel prediction-widget">
      <div className="widget-header">
        <BrainCircuit size={24} color={neonColor} />
        <h3>AI Prediction (15 Menit Kedepan)</h3>
      </div>
      
      <div className="prediction-content">
        <div className="status-ring" style={{ borderColor: neonColor }}>
          <span className="status-value">{current.density_per_5s}</span>
          <span className="status-label">kendaraan/5s</span>
        </div>
        
        <h4 className="prediction-message" style={{ color: neonColor }}>{prediction.status}</h4>
        <p className="prediction-desc">
          {prediction.desc}
        </p>
      </div>
    </div>
  );
}
