import { useNavigate } from "react-router-dom";

function Profile({ user, onLogout }) {
  const navigate = useNavigate();

  function handleLogout() {
    onLogout();
    navigate("/");
  }

  return (
    <main className="page">
      <h1>Profile</h1>
      <p>Signed in as <strong>{user}</strong></p>
      <button className="btn-primary" onClick={handleLogout}>Log out</button>
    </main>
  );
}

export default Profile;