"use client";

import { useEffect, useState } from "react";

const stops = [
  { id: "data", label: "Data" },
  { id: "model", label: "Mechanism" },
  { id: "simulator", label: "Try it" },
  { id: "fit", label: "Model fit" },
  { id: "evidence", label: "Evidence" },
  { id: "conclusion", label: "Conclusion" },
  { id: "methods", label: "Sources" },
];

export default function ResearchPath() {
  const [active, setActive] = useState("");
  useEffect(() => {
    let frame = 0;
    const update = () => {
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(() => {
        let current = "";
        for (const stop of stops) {
          const section = document.getElementById(stop.id);
          if (section && section.getBoundingClientRect().top <= 160) current = stop.id;
        }
        setActive(current);
      });
    };
    update();
    window.addEventListener("scroll", update, { passive: true });
    window.addEventListener("resize", update);
    return () => { cancelAnimationFrame(frame); window.removeEventListener("scroll", update); window.removeEventListener("resize", update); };
  }, []);

  return <nav className="research-path" aria-label="Explore the analysis">
    <div className="research-path-inner">
      {stops.map((stop, index) => <a key={stop.id} href={`#${stop.id}`} onClick={() => setActive(stop.id)}
        className={active === stop.id ? "is-active" : ""} aria-current={active === stop.id ? "location" : undefined}>
        <span>{String(index + 1).padStart(2, "0")}</span>{stop.label}
      </a>)}
    </div>
  </nav>;
}
