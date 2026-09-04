// src/components/layout/AppLayout.tsx
import { Outlet } from "react-router";
import Sidebar from "./Sidebar";

function AppLayout() {
    return (
        <div className="app-layout">
            <Sidebar />

            <main className="app-layout__main">
                <Outlet />
            </main>
        </div>
    );
}

export default AppLayout;
