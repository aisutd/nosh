import CookingMemory from '../components/CookingMemory.jsx';
import { Link } from 'react-router-dom';
import { useNavigate } from "react-router-dom";

function Profile({ user, onLogout }) {
  const navigate = useNavigate();

  function handleLogout() {
    onLogout();
    navigate("/");
  }

  if (!user) return <main className="page"><h1>Profile</h1><p><Link to="/auth">Log in</Link> to save your cooking preferences and history.</p></main>;

  return (
    <main className="page">
      <h1>Profile</h1>
      <p>Signed in as <strong>{user}</strong></p>
      <CookingMemory key={user} />
      <button className="btn-primary" onClick={handleLogout}>Log out</button>
    </main>
  );
}

export default Profile;