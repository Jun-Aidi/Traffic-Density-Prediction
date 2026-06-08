import Navbar from './components/Navbar'
import LiveCCTV from './components/LiveCCTV'
import PredictionWidget from './components/PredictionWidget'
import TrafficChart from './components/TrafficChart'
import './App.css'

function App() {
  return (
    <div className="app-container">
      <Navbar />
      
      <main className="dashboard-main">
        <header className="page-header">
          <h1>Traffic Radar</h1>
          <p>Pantau langsung kondisi lalu lintas Gelora 0-17 dan rencanakan rute Anda.</p>
        </header>

        <div className="dashboard-grid">
          {/* Kolom Kiri: Video CCTV */}
          <div className="left-column">
            <LiveCCTV />
          </div>

          {/* Kolom Kanan: Widget Prediksi & Grafik */}
          <div className="right-column">
            <PredictionWidget />
            <TrafficChart />
          </div>
        </div>
      </main>
    </div>
  )
}

export default App
