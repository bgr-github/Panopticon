import TotalEventsPanel from "../components/ui/dashboard/TotalEventsPanel";

function DashboardPage() {
    return (
        <div className="dashboard-page">
            <header className="dashboard-page__header">
                <div>
                    <h1>Dashboard</h1>
                    <p>Live honeypot activity overview</p>
                </div>

                <div className="dashboard-page__actions">Actions</div>
            </header>

            <section className="dashboard-kpis" aria-label="Dashboard metrics">
                <article className="dashboard-card">
                    <TotalEventsPanel />
                </article>
                <article className="dashboard-card">Active Sessions</article>
                <article className="dashboard-card">Unique Sources</article>
                <article className="dashboard-card">Commands</article>
                <article className="dashboard-card">File Transfers</article>
            </section>

            <section className="dashboard-orbit-grid">
                <article className="dashboard-panel dashboard-panel--severity">
                    Severity Breakdown
                </article>
                <article className="dashboard-panel dashboard-panel--recent">
                    Recent Events
                </article>
                <article className="dashboard-panel dashboard-panel--sessions">
                    Active Sessions
                </article>

                <article className="dashboard-panel dashboard-panel--commands">
                    Top Commands
                </article>
                <main className="dashboard-panel dashboard-map">
                    Live Attack Map
                </main>
                <article className="dashboard-panel dashboard-panel--sources">
                    Top Sources
                </article>

                <article className="dashboard-panel dashboard-panel--timeline">
                    Event Timeline
                </article>
                <article className="dashboard-panel dashboard-panel--files">
                    File Activity
                </article>
            </section>
        </div>
    );
}

export default DashboardPage;
