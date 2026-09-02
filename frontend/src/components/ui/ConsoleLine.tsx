import type { HoneypotEvent } from "../../data/types";

type Props = {
  event: HoneypotEvent;
};

function ConsoleLine({ event }: Props) {
  return (
    <li>
      <strong>{event.event_type}</strong>{" "}
      <span>
        {event.src_ip}:{event.src_port}
      </span>{" "}
      <code>{event.input}</code>
    </li>
  );
}

export default ConsoleLine;
