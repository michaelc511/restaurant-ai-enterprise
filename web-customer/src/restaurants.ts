// F5: one customer site, three restaurants. Each entry pairs a cuisine (engine_api.py's `cuisine`)
// with its menu (parsed from the PDF by scripts/build_menus.py), the PDF itself, a colour theme,
// artwork and the AI host's greeting. Everything factual comes from the menu JSON.
import type { ComponentType, CSSProperties } from "react";
import sushiMenu from "./menus/sushi.json";
import steakMenu from "./menus/steak.json";
import italianMenu from "./menus/italian.json";
import sushiPdf from "../../domains/restaurant/docs/sushi.pdf?url";
import steakPdf from "../../domains/restaurant/docs/steak.pdf?url";
import italianPdf from "../../domains/restaurant/docs/italian.pdf?url";
import { EmberMark, ItalianTable, OliveMark, SakuraBranch, SakuraFlower, SteakBoard, SushiBoard } from "./art";

export interface MenuItem {
  name: string;
  price: number;
  tags: string[];
  description: string;
}
export interface MenuSection {
  title: string;
  items: MenuItem[];
}
export interface RestaurantInfo {
  name: string;
  tagline: string;
  address: string | null;
  hours: string | null;
  payment: string | null;
  reservations: string | null;
  takeout: string | null;
  parking: string | null;
  dress: string | null;
  alcohol: string | null;
}
export interface Restaurant {
  cuisine: "sushi" | "steak" | "italian";
  label: string;
  short: string; // brand word in the header
  place: string; // eyebrow above the name, from the PDF address
  info: RestaurantInfo;
  sections: MenuSection[];
  pdfUrl: string;
  theme: CSSProperties;
  Mark: ComponentType<{ size?: number }>;
  Hero: ComponentType<{ className?: string }>;
  Branch?: ComponentType<{ className?: string }>;
  hostName: string;
  greeting: string;
  suggested: string[];
}

const vars = (v: Record<string, string>) => v as CSSProperties;

export const RESTAURANTS: Restaurant[] = [
  {
    cuisine: "sushi",
    label: "Sushi",
    short: "Sakura",
    place: "Seattle · Downtown Arts District",
    info: sushiMenu.info,
    sections: sushiMenu.sections,
    pdfUrl: sushiPdf,
    theme: vars({
      "--accent": "#c8442f", "--accent-dark": "#a63523", "--soft": "#f6c1cf", "--soft-deep": "#e48aa3",
      "--soft-bg": "#fdf2f5", "--glow": "rgba(246,193,207,.28)", "--paper": "#fbf7f0", "--paper-2": "#f3ece0",
    }),
    Mark: SakuraFlower,
    Hero: SushiBoard,
    Branch: SakuraBranch,
    hostName: "Sakura AI host",
    greeting: "Konnichiwa! I'm the Sakura Sushi & Izakaya Lounge AI host. Ask me anything about our menu: dishes, prices, dietary options or hours.",
    suggested: [
      "What do you recommend for a first visit?",
      "Which dishes are vegan or vegetarian?",
      "Do I need a reservation for omakase?",
      "What's spicy on the menu?",
    ],
  },
  {
    cuisine: "steak",
    label: "Steakhouse",
    short: "Prime & Ember",
    place: "Chicago · Financial Center",
    info: steakMenu.info,
    sections: steakMenu.sections,
    pdfUrl: steakPdf,
    theme: vars({
      "--accent": "#b4432a", "--accent-dark": "#8f3220", "--soft": "#f3d2b8", "--soft-deep": "#d98b5f",
      "--soft-bg": "#fbf0e7", "--glow": "rgba(217,139,95,.2)", "--paper": "#f8f5f1", "--paper-2": "#efe8df",
    }),
    Mark: EmberMark,
    Hero: SteakBoard,
    hostName: "Prime & Ember AI host",
    greeting: "Good evening! I'm the Prime & Ember Steakhouse AI host. Ask me about our cuts, sides, wine, prices or reservations.",
    suggested: [
      "Which steak would you recommend for two?",
      "What's the difference between the filet and the ribeye?",
      "Do you have gluten-free options?",
      "Do I need a reservation?",
    ],
  },
  {
    cuisine: "italian",
    label: "Italian",
    short: "Bella Vista",
    place: "Springfield, Oregon",
    info: italianMenu.info,
    sections: italianMenu.sections,
    pdfUrl: italianPdf,
    theme: vars({
      "--accent": "#c0392b", "--accent-dark": "#962c21", "--soft": "#dfe8c8", "--soft-deep": "#8ea05a",
      "--soft-bg": "#f3f6ea", "--glow": "rgba(142,160,90,.2)", "--paper": "#fbf8f1", "--paper-2": "#f1ecdf",
    }),
    Mark: OliveMark,
    Hero: ItalianTable,
    hostName: "Bella Vista AI host",
    greeting: "Benvenuti! I'm the Bella Vista Italian Trattoria AI host. Ask me about our pasta, wood-fired dishes, wine, prices or hours.",
    suggested: [
      "What pasta do you recommend?",
      "Which dishes are vegetarian?",
      "Do you take reservations?",
      "What desserts do you have?",
    ],
  },
];

export const restaurantFor = (cuisine: string | null): Restaurant =>
  RESTAURANTS.find((r) => r.cuisine === cuisine) ?? RESTAURANTS[0];
