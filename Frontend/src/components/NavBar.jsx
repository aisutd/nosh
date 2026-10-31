import { NavLink } from "react-router-dom";
import { LuRefrigerator, LuFlame, LuHeart, LuUser } from "react-icons/lu";

function NavBar({ user }) {
  return (
    <nav className="navbar">
      <NavLink to="/pantry" end className="nav-item">
        <LuRefrigerator size={22} />
        <span>Pantry</span>
      </NavLink>

      <NavLink to="/swipe" className="nav-item">
        <LuFlame size={22} />
        <span>Swipe</span>
      </NavLink>

      <NavLink to="/saved" className="nav-item">
        <LuHeart size={22} />
        <span>Saved</span>
      </NavLink>

      {user ? (
        <NavLink to="/profile" className="nav-item">
          <LuUser size={22} />
          <span>Me</span>
        </NavLink>
      ) : (
        <NavLink to="/auth" className="nav-item">
          <LuUser size={22} />
          <span>Log in</span>
        </NavLink>
      )}
    </nav>
  );
}

export default NavBar;