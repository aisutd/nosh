import { NavLink, useLocation } from "react-router-dom";
import { LuRefrigerator, LuFlame, LuHeart, LuUser } from "react-icons/lu";

function NavBar({ user }) {
  const { pathname } = useLocation();

  // true if the current page is one of these addresses (or a page under it)
  const isOn = (paths) =>
    paths.some((p) => pathname === p || (p !== "/" && pathname.startsWith(p + "/")));

  // one class string per tab: "nav-item" plus "active" when it should be orange
  const tab = (paths) => `nav-item ${isOn(paths) ? "active" : ""}`;

  return (
    <nav className="navbar">
      <NavLink to="/pantry" className={() => tab(["/", "/pantry"])}>
        <LuRefrigerator size={22} />
        <span>Pantry</span>
      </NavLink>

      <NavLink to="/swipe" className={() => tab(["/swipe"])}>
        <LuFlame size={22} />
        <span>Swipe</span>
      </NavLink>

      <NavLink to="/saved" className={() => tab(["/saved", "/cook"])}>
        <LuHeart size={22} />
        <span>Saved</span>
      </NavLink>

      {user ? (
        <NavLink to="/profile" className={() => tab(["/profile", "/inventory"])}>
          <LuUser size={22} />
          <span>Me</span>
        </NavLink>
      ) : (
        <NavLink to="/auth" className={() => tab(["/auth"])}>
          <LuUser size={22} />
          <span>Log in</span>
        </NavLink>
      )}
    </nav>
  );
}

export default NavBar;