// F5: original inline SVG illustrations for the customer site (no third-party or stock images).
// Colours come from CSS variables so the art matches the page palette.
import type React from "react";

export function SakuraFlower({ size = 28, className }: { size?: number; className?: string }) {
  const petals = [0, 72, 144, 216, 288];
  return (
    <svg className={className} width={size} height={size} viewBox="-20 -20 40 40" aria-hidden="true">
      {petals.map((deg) => (
        <path
          key={deg}
          transform={`rotate(${deg})`}
          d="M0 -2 C 6 -6, 8 -14, 2 -17 L 0 -14 L -2 -17 C -8 -14, -6 -6, 0 -2 Z"
          fill="var(--sakura)"
          stroke="var(--sakura-deep)"
          strokeWidth="0.8"
        />
      ))}
      <circle r="3" fill="var(--gold)" />
    </svg>
  );
}

export function SakuraBranch({ className }: { className?: string }) {
  const blossoms: [number, number, number][] = [
    [70, 42, 30], [128, 66, 24], [182, 40, 32], [238, 80, 22], [290, 52, 28], [342, 92, 20], [210, 120, 18],
  ];
  return (
    <svg className={className} viewBox="0 0 400 160" aria-hidden="true">
      <path d="M0 30 C 80 40, 140 70, 220 75 S 360 110, 400 150" fill="none" stroke="var(--bark)" strokeWidth="6" strokeLinecap="round" />
      <path d="M150 68 C 170 50, 175 35, 182 40" fill="none" stroke="var(--bark)" strokeWidth="3" strokeLinecap="round" />
      <path d="M260 88 C 280 70, 286 56, 290 52" fill="none" stroke="var(--bark)" strokeWidth="3" strokeLinecap="round" />
      <path d="M200 76 C 205 95, 208 110, 210 120" fill="none" stroke="var(--bark)" strokeWidth="2.5" strokeLinecap="round" />
      {blossoms.map(([x, y, s]) => (
        <g key={`${x}-${y}`} transform={`translate(${x} ${y}) scale(${s / 40})`}>
          {[0, 72, 144, 216, 288].map((deg) => (
            <path key={deg} transform={`rotate(${deg})`} d="M0 -2 C 6 -6, 8 -14, 2 -17 L 0 -14 L -2 -17 C -8 -14, -6 -6, 0 -2 Z" fill="var(--sakura)" stroke="var(--sakura-deep)" strokeWidth="0.8" />
          ))}
          <circle r="3" fill="var(--gold)" />
        </g>
      ))}
    </svg>
  );
}

/** Hero: a wooden geta board with salmon and tuna nigiri, a maki roll, wasabi, ginger and chopsticks. */
export function SushiBoard({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 520 360" role="img" aria-label="Illustration of a sushi board with nigiri and maki">
      <ellipse cx="260" cy="300" rx="230" ry="26" fill="rgba(0,0,0,.12)" />
      {/* board */}
      <rect x="40" y="170" width="440" height="110" rx="14" fill="var(--wood)" />
      <rect x="40" y="170" width="440" height="22" rx="10" fill="var(--wood-light)" />
      <rect x="90" y="280" width="40" height="20" rx="4" fill="var(--wood-dark)" />
      <rect x="390" y="280" width="40" height="20" rx="4" fill="var(--wood-dark)" />
      {/* salmon nigiri */}
      <g transform="translate(80 120)">
        <ellipse cx="60" cy="72" rx="58" ry="24" fill="#fbfaf6" stroke="#e7e1d4" strokeWidth="2" />
        <path d="M2 62 C 20 20, 100 20, 120 58 C 100 66, 30 70, 2 62 Z" fill="var(--salmon)" />
        <path d="M22 50 C 40 38, 70 34, 96 44" stroke="#fff" strokeOpacity=".7" strokeWidth="5" fill="none" strokeLinecap="round" />
        <path d="M14 58 C 34 46, 74 42, 110 54" stroke="#fff" strokeOpacity=".5" strokeWidth="4" fill="none" strokeLinecap="round" />
      </g>
      {/* tuna nigiri */}
      <g transform="translate(210 112)">
        <ellipse cx="60" cy="80" rx="58" ry="24" fill="#fbfaf6" stroke="#e7e1d4" strokeWidth="2" />
        <path d="M2 70 C 20 26, 100 26, 120 66 C 100 74, 30 78, 2 70 Z" fill="var(--tuna)" />
        <path d="M30 54 C 50 44, 76 42, 98 50" stroke="#fff" strokeOpacity=".35" strokeWidth="4" fill="none" strokeLinecap="round" />
        <rect x="52" y="34" width="16" height="50" rx="3" fill="var(--nori)" />
      </g>
      {/* maki rolls */}
      <g transform="translate(350 128)">
        {[0, 52].map((dx) => (
          <g key={dx} transform={`translate(${dx} 0)`}>
            <ellipse cx="24" cy="64" rx="24" ry="9" fill="#1d2b22" />
            <rect x="0" y="22" width="48" height="42" fill="var(--nori)" />
            <ellipse cx="24" cy="22" rx="24" ry="9" fill="#fbfaf6" stroke="var(--nori)" strokeWidth="4" />
            <circle cx="24" cy="22" r="5" fill="var(--salmon)" />
            <circle cx="16" cy="21" r="2.5" fill="#7cb46b" />
          </g>
        ))}
      </g>
      {/* wasabi + ginger */}
      <path d="M418 220 C 430 196, 456 196, 462 222 Z" fill="#8bbf4f" />
      <path d="M380 228 C 392 206, 412 210, 414 228 C 404 236, 388 236, 380 228 Z" fill="var(--sakura)" />
      {/* chopsticks */}
      <rect x="70" y="92" width="380" height="9" rx="4.5" fill="var(--bark)" transform="rotate(-10 260 96)" />
      <rect x="80" y="110" width="380" height="9" rx="4.5" fill="var(--bark)" transform="rotate(-8 270 114)" />
      {/* petals */}
      <g opacity=".9">
        <ellipse cx="36" cy="60" rx="8" ry="5" fill="var(--sakura)" transform="rotate(30 36 60)" />
        <ellipse cx="480" cy="70" rx="9" ry="5" fill="var(--sakura)" transform="rotate(-25 480 70)" />
        <ellipse cx="300" cy="30" rx="7" ry="4" fill="var(--sakura)" transform="rotate(10 300 30)" />
      </g>
    </svg>
  );
}

export function CategoryIcon({ category, size = 40 }: { category: string; size?: number }) {
  const c = category.toLowerCase();
  if (c.startsWith("appetizer")) {
    // edamame pods
    return (
      <svg width={size} height={size} viewBox="0 0 48 48" aria-hidden="true">
        <path d="M8 34 C 8 18, 26 8, 40 12 C 38 28, 22 40, 8 34 Z" fill="#7cb46b" />
        {[[18, 28], [25, 22], [32, 17]].map(([x, y]) => <circle key={x} cx={x} cy={y} r="4.5" fill="#a5d48d" />)}
      </svg>
    );
  }
  if (c.startsWith("entr")) {
    // nigiri
    return (
      <svg width={size} height={size} viewBox="0 0 48 48" aria-hidden="true">
        <ellipse cx="24" cy="32" rx="18" ry="8" fill="#fbfaf6" stroke="#e7e1d4" />
        <path d="M6 29 C 12 14, 36 14, 42 28 C 34 32, 14 33, 6 29 Z" fill="var(--salmon)" />
        <path d="M14 24 C 20 20, 28 19, 34 22" stroke="#fff" strokeOpacity=".7" strokeWidth="2.5" fill="none" strokeLinecap="round" />
      </svg>
    );
  }
  if (c.startsWith("dessert")) {
    // mochi trio
    return (
      <svg width={size} height={size} viewBox="0 0 48 48" aria-hidden="true">
        <ellipse cx="14" cy="32" rx="10" ry="8" fill="#b8d98a" />
        <ellipse cx="34" cy="32" rx="10" ry="8" fill="#f6c86b" />
        <ellipse cx="24" cy="22" rx="10" ry="8" fill="#5b5552" />
      </svg>
    );
  }
  // tea cup
  return (
    <svg width={size} height={size} viewBox="0 0 48 48" aria-hidden="true">
      <path d="M10 18 H38 C 38 34, 30 40, 24 40 C 18 40, 10 34, 10 18 Z" fill="var(--tea)" />
      <rect x="10" y="16" width="28" height="4" rx="2" fill="#2f5d4a" />
      <path d="M18 12 C 16 8, 20 6, 18 2 M26 12 C 24 8, 28 6, 26 2" stroke="#b9b3a8" strokeWidth="2" fill="none" strokeLinecap="round" />
    </svg>
  );
}

export function AiAvatar({ size = 34, mark }: { size?: number; mark?: React.ReactNode }) {
  return (
    <span className="avatar" style={{ width: size, height: size }} aria-hidden="true">
      {mark}
    </span>
  );
}

// ---------------------------------------------------------------- steakhouse (Prime & Ember)

export function EmberMark({ size = 28 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 40 40" aria-hidden="true">
      <path d="M20 3 C 27 12, 33 17, 33 25 A 13 13 0 0 1 7 25 C 7 18, 12 14, 14 9 C 16 14, 18 16, 20 17 C 21 12, 20 8, 20 3 Z" fill="var(--accent)" />
      <path d="M20 17 C 25 22, 26 25, 26 28 A 6 6 0 0 1 14 28 C 14 25, 16 23, 17 21 C 18 23, 19 24, 20 24 Z" fill="var(--gold)" />
    </svg>
  );
}

/** Hero: a sliced ribeye on a carving board, rosemary, a glass of red wine and grill flames. */
export function SteakBoard({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 520 360" role="img" aria-label="Illustration of a sliced steak on a board with rosemary and red wine">
      <ellipse cx="250" cy="312" rx="220" ry="22" fill="rgba(0,0,0,.14)" />
      {/* smoke from the grill */}
      <g fill="none" stroke="#b9b1a4" strokeWidth="5" strokeLinecap="round" opacity=".55">
        <path d="M120 140 C 100 118, 140 104, 118 80 C 104 64, 124 50, 116 34" />
        <path d="M200 132 C 182 112, 220 98, 198 74 C 186 60, 204 48, 198 30" />
        <path d="M280 140 C 262 120, 298 106, 278 84 C 266 70, 284 58, 276 44" />
      </g>
      {/* board */}
      <rect x="30" y="200" width="380" height="96" rx="20" fill="var(--wood)" />
      <rect x="30" y="200" width="380" height="18" rx="12" fill="var(--wood-light)" />
      <circle cx="388" cy="248" r="10" fill="var(--wood-dark)" />
      {/* steak slices */}
      {[0, 1, 2, 3, 4].map((i) => (
        <g key={i} transform={`translate(${70 + i * 52} ${150 - (i % 2) * 4}) rotate(${-8 + i * 4})`}>
          <rect x="0" y="0" width="58" height="66" rx="16" fill="var(--sear)" />
          <rect x="7" y="9" width="44" height="48" rx="12" fill="var(--meat)" />
          <rect x="16" y="20" width="26" height="26" rx="9" fill="var(--meat-pink)" />
          <path d="M6 12 L 52 16 M6 30 L 52 34 M6 48 L 52 52" stroke="#2a1712" strokeWidth="3" opacity=".55" />
        </g>
      ))}
      {/* rosemary */}
      <path d="M60 236 C 120 226, 180 230, 230 222" stroke="#4f6b3a" strokeWidth="3" fill="none" />
      {Array.from({ length: 9 }, (_, i) => (
        <ellipse key={i} cx={74 + i * 18} cy={231 - i * 1.2} rx="9" ry="2.6" fill="#6f8f4f" transform={`rotate(${i % 2 ? 30 : -30} ${74 + i * 18} ${231 - i * 1.2})`} />
      ))}
      {/* salt */}
      {[[250, 236], [262, 244], [276, 238], [290, 246]].map(([x, y]) => <rect key={x} x={x} y={y} width="5" height="5" fill="#f2efe8" transform={`rotate(20 ${x} ${y})`} />)}
      {/* wine glass */}
      <g transform="translate(430 70)">
        <path d="M0 0 H56 C 58 50, 44 78, 28 80 C 12 78, -2 50, 0 0 Z" fill="rgba(255,255,255,.55)" stroke="#c9c2b6" strokeWidth="2" />
        <path d="M3 38 H53 C 50 62, 40 76, 28 77 C 16 76, 6 62, 3 38 Z" fill="var(--wine)" />
        <rect x="26" y="80" width="4" height="120" fill="#c9c2b6" />
        <ellipse cx="28" cy="202" rx="26" ry="6" fill="#c9c2b6" />
      </g>
    </svg>
  );
}

// ---------------------------------------------------------------- trattoria (Bella Vista)

export function OliveMark({ size = 28 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 40 40" aria-hidden="true">
      <path d="M6 34 C 14 26, 22 18, 34 6" stroke="var(--olive-dark)" strokeWidth="2.5" fill="none" strokeLinecap="round" />
      {[[12, 26, -40], [18, 20, 40], [22, 15, -40], [28, 10, 40]].map(([x, y, r]) => (
        <ellipse key={x} cx={x} cy={y} rx="6" ry="2.6" fill="var(--olive)" transform={`rotate(${r} ${x} ${y})`} />
      ))}
      <ellipse cx="15" cy="30" rx="3.4" ry="4.2" fill="var(--accent)" />
    </svg>
  );
}

/** Hero: a wood-fired margherita pizza on a peel, a bowl of spaghetti, basil and tomatoes. */
export function ItalianTable({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 520 360" role="img" aria-label="Illustration of a margherita pizza, a bowl of spaghetti, basil and tomatoes">
      <ellipse cx="260" cy="318" rx="230" ry="20" fill="rgba(0,0,0,.12)" />
      {/* pizza peel */}
      <rect x="250" y="168" width="230" height="16" rx="8" fill="var(--wood-dark)" />
      <circle cx="190" cy="200" r="132" fill="var(--wood)" />
      {/* pizza */}
      <circle cx="190" cy="200" r="116" fill="#e9b96e" />
      <circle cx="190" cy="200" r="100" fill="var(--accent)" />
      {[[150, 160], [222, 168], [176, 228], [236, 234], [140, 222], [196, 192]].map(([x, y]) => (
        <ellipse key={`${x}${y}`} cx={x} cy={y} rx="20" ry="16" fill="#fbf4e4" />
      ))}
      {[[164, 186, 20], [214, 204, -30], [190, 250, 50], [140, 248, -10]].map(([x, y, r]) => (
        <ellipse key={`b${x}`} cx={x} cy={y} rx="11" ry="6" fill="var(--olive)" transform={`rotate(${r} ${x} ${y})`} />
      ))}
      {[[110, 196], [276, 214], [190, 108], [168, 296]].map(([x, y]) => <circle key={`c${x}`} cx={x} cy={y} r="5" fill="#c98f43" opacity=".7" />)}
      {/* pasta bowl */}
      <g transform="translate(330 196)">
        <ellipse cx="80" cy="74" rx="80" ry="20" fill="#e9e2d4" />
        <path d="M0 40 H160 C 156 84, 120 100, 80 100 C 40 100, 4 84, 0 40 Z" fill="#fbfaf6" stroke="#e1d8c6" strokeWidth="2" />
        <path d="M2 40 C 2 38, 158 38, 158 40" stroke="var(--olive-dark)" strokeWidth="3" />
        <ellipse cx="80" cy="40" rx="78" ry="16" fill="#f1cf7a" />
        {[0, 1, 2, 3, 4, 5].map((i) => (
          <path key={i} d={`M${20 + i * 22} 36 C ${30 + i * 22} 22, ${44 + i * 22} 50, ${54 + i * 22} 32`} stroke="#e2b85a" strokeWidth="3" fill="none" />
        ))}
        <ellipse cx="80" cy="32" rx="34" ry="11" fill="var(--accent)" />
        <ellipse cx="88" cy="26" rx="9" ry="5" fill="var(--olive)" transform="rotate(-20 88 26)" />
      </g>
      {/* tomatoes */}
      {[[60, 64], [92, 52], [76, 88]].map(([x, y]) => (
        <g key={x}>
          <circle cx={x} cy={y} r="17" fill="var(--accent)" />
          <path d={`M${x - 6} ${y - 16} L ${x} ${y - 10} L ${x + 6} ${y - 16}`} stroke="var(--olive-dark)" strokeWidth="3" fill="none" />
        </g>
      ))}
    </svg>
  );
}

/** Menu-section icons that match each restaurant. */
export function CuisineIcon({ cuisine, category, size = 28 }: { cuisine: string; category: string; size?: number }) {
  if (cuisine === "sushi") return <CategoryIcon category={category} size={size} />;
  const c = category.toLowerCase();
  const s = { width: size, height: size, viewBox: "0 0 48 48", "aria-hidden": true } as const;
  if (c.startsWith("bever")) {
    return (
      <svg {...s}>
        <path d="M14 6 H34 C 35 22, 30 30, 24 30 C 18 30, 13 22, 14 6 Z" fill="rgba(0,0,0,.06)" stroke="#b9b1a4" strokeWidth="1.5" />
        <path d="M15 16 H33 C 32 25, 28 29, 24 29 C 20 29, 16 25, 15 16 Z" fill="var(--wine)" />
        <rect x="23" y="30" width="2" height="10" fill="#b9b1a4" />
        <ellipse cx="24" cy="41" rx="9" ry="2.5" fill="#b9b1a4" />
      </svg>
    );
  }
  if (c.startsWith("dessert")) {
    return cuisine === "steak" ? (
      <svg {...s}>
        <path d="M6 34 L 40 34 L 40 26 L 12 16 Z" fill="#f6e7c8" />
        <path d="M6 34 L 40 34 L 40 30 L 6 30 Z" fill="#c98f5b" />
        <path d="M12 16 L 40 26 L 40 24 L 14 14 Z" fill="var(--accent)" />
      </svg>
    ) : (
      <svg {...s}>
        <rect x="8" y="14" width="32" height="22" rx="3" fill="#f6ead6" />
        <rect x="8" y="14" width="32" height="5" fill="#6b4a33" />
        <rect x="8" y="25" width="32" height="3" fill="#c9a27a" />
        {[13, 21, 29, 35].map((x) => <circle key={x} cx={x} cy="16" r="1.2" fill="#3e2a1f" />)}
      </svg>
    );
  }
  if (c.startsWith("entr")) {
    return cuisine === "steak" ? (
      <svg {...s}>
        <path d="M8 26 C 8 12, 26 8, 36 14 C 44 19, 42 34, 30 36 C 22 38, 8 38, 8 26 Z" fill="var(--sear)" />
        <path d="M14 26 C 14 16, 26 13, 33 17 C 38 21, 36 30, 29 31 C 23 32, 14 33, 14 26 Z" fill="var(--meat)" />
        <path d="M14 20 L 36 28 M12 28 L 32 34" stroke="#2a1712" strokeWidth="2" opacity=".5" />
      </svg>
    ) : (
      <svg {...s}>
        <path d="M6 22 H42 C 41 34, 33 40, 24 40 C 15 40, 7 34, 6 22 Z" fill="#fbfaf6" stroke="#e1d8c6" />
        <ellipse cx="24" cy="22" rx="18" ry="5" fill="#f1cf7a" />
        <ellipse cx="24" cy="20" rx="8" ry="3" fill="var(--accent)" />
        <path d="M30 4 L 26 21 M34 5 L 28 21" stroke="#9a8f80" strokeWidth="2" />
      </svg>
    );
  }
  // appetizers
  return cuisine === "steak" ? (
    <svg {...s}>
      <path d="M8 30 C 8 18, 20 10, 30 14 C 40 18, 42 30, 34 36 C 26 42, 8 40, 8 30 Z" fill="#cfd3d6" />
      <path d="M13 29 C 14 21, 22 16, 29 19 C 35 22, 35 29, 30 32 C 25 35, 13 35, 13 29 Z" fill="#efe9de" />
      <circle cx="24" cy="26" r="3" fill="#d7c8a8" />
    </svg>
  ) : (
    <svg {...s}>
      <rect x="6" y="20" width="36" height="14" rx="6" fill="#e2b26b" />
      {[12, 20, 28, 36].map((x) => <circle key={x} cx={x} cy="19" r="3.6" fill="var(--accent)" />)}
      {[16, 32].map((x) => <ellipse key={x} cx={x} cy="16" rx="3.6" ry="2" fill="var(--olive)" />)}
    </svg>
  );
}
