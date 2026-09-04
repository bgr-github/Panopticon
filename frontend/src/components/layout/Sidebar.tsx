// src/components/layout/Sidebar.tsx
import { NavLink } from "react-router";

function Sidebar() {
    return (
        <aside className="sidebar">
            <div className="sidebar__brand">Panopticon</div>

            <nav className="sidebar__nav">
                <NavLink to="/">Dashboard</NavLink>
                <NavLink to="/events">Events</NavLink>
                <NavLink to="/sessions">Sessions</NavLink>
                <NavLink to="/settings">Settings</NavLink>
            </nav>
        </aside>
    );
}

export default Sidebar;
