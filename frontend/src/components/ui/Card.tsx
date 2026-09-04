import react from "react";

type Props = {
  children: react.ReactNode;
};

export function Card({ children }: Props) {
  return <div className="card">{children}</div>;
}

export default Card;
