import { Car, Bell, User, MapPin } from 'lucide-react';

export default function Navbar() {
  return (
    <nav className="navbar">
      <div className="nav-brand">
        <Car className="brand-icon" size={28} />
        GeloraRadar
      </div>
      
      <div className="nav-profile">
        <MapPin size={20} color="var(--text-muted)" />
        <span>Gelora 0-17, Jakarta</span>
        
        <div style={{ width: '1px', height: '24px', background: 'var(--border-color)', margin: '0 8px' }}></div>
        
        <Bell size={20} color="var(--text-muted)" />
        <div className="avatar">
          <User size={20} />
        </div>
      </div>
    </nav>
  );
}
