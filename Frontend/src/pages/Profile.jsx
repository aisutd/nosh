import CookingMemory from '../components/CookingMemory.jsx';
import { Link, useNavigate } from "react-router-dom";

function Profile({ user, onLogout }) {
  const navigate = useNavigate();

  function handleLogout() {
    onLogout();
    navigate("/");
  }

  if (!user) return <main className="page"><h1>Profile</h1><Link to="/auth">Log in to see your preferences</Link></main>;

  return (
    <main className="page profile-page">
      <span className="profile-avatar" aria-hidden="true">{String(user || "N").slice(0, 1).toUpperCase()}</span>
      <h1>My kitchen</h1>
      <p>Signed in as <strong>{user}</strong></p>

      <Link to="/inventory" className="cta">My inventory</Link>

      <CookingMemory key={user} />
      <button className="btn-primary" onClick={handleLogout}>Log out</button>
    </main>
  );
}

export default Profile;