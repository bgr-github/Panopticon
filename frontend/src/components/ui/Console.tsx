import ConsoleLine from "./ConsoleLine";
import type { HoneypotEvent } from "../../data/types";
import { useState, useEffect } from "react";

function Console() {
  const [events, setEvents] = useState<HoneypotEvent[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const fetchData = async function () {
      let buffer: string = "";

      try {
        setLoading(true);

        // Open HTTP connection to api
        const response = await fetch("http://127.0.0.1:8000/events/stream");

        if (!response.ok || !response.body) {
          throw new Error(response.statusText);
        }

        // Read event chunks
        const reader = response.body.getReader();
        const decoder = new TextDecoder();

        while (true) {
          const { value, done } = await reader.read();

          if (done) {
            setLoading(false);
            break;
          }

          // Add to a buffer as streaming doesn't promise full message delivery
          buffer += decoder.decode(value, { stream: true });

          const messages = buffer.split("\n\n");
          buffer = messages.pop() ?? "";

          for (const message of messages) {
            const line = message
              .split("\n")
              .find((item) => item.startsWith("data: "));

            if (!line) {
              continue;
            }

            const json = line.slice("data: ".length);
            const event = JSON.parse(json) as HoneypotEvent;

            setEvents((current) => {
              if (current.some((item) => item.id === event.id)) {
                return current;
              }

              return [event, ...current].slice(0, 100);
            });
          }
        }
      } catch {
        setLoading(false);
      }
    };

    fetchData();
  }, []);

  return (
    <div className="console">
      {loading && events.length === 0 && <i>Waiting for events...</i>}

      <ul>
        {events.map((event) => (
          <ConsoleLine key={event.id} event={event} />
        ))}
      </ul>
    </div>
  );
}

export default Console;
