import { useState, useEffect } from "react";
import { Card } from "../Card";

function TotalEventsPanel() {
    const [totalEvents, setTotalEvents] = useState<number | null>(null);

    useEffect(() => {
        const fetchTotalEvents = async () => {
            try {
                const response = await fetch(
                    "http://127.0.0.1:8000/events/number"
                );
                const total: number = await response.json();
                setTotalEvents(total);
            } catch (error) {
                console.error("Error fetching total events:", error);
            }
        };

        fetchTotalEvents();
    }, []);

    return <Card>Total Events: {totalEvents}</Card>;
}

export default TotalEventsPanel;
