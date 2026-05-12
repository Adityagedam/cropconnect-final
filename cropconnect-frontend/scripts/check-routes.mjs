import { readFileSync } from "node:fs";

const appSource = readFileSync(new URL("../src/App.jsx", import.meta.url), "utf8").replace(/\s+/g, " ");
const translationSource = readFileSync(new URL("../src/components/landing/LandingLanguageContext.jsx", import.meta.url), "utf8");

const requiredProtectedRoutes = [
  ['path="/dashboard"', "<ProtectedPage><Dashboard /></ProtectedPage>"],
  ['path="/crop-planner"', "<ProtectedPage><CropPlanner /></ProtectedPage>"],
];

const failures = requiredProtectedRoutes.filter(([route, wrapper]) => {
  const routeIndex = appSource.indexOf(route);
  if (routeIndex === -1) return true;
  const routeSnippet = appSource.slice(routeIndex, routeIndex + 220);
  return !routeSnippet.includes(wrapper);
});

if (failures.length) {
  console.error(
    `Protected route check failed for: ${failures.map(([route]) => route.replace('path="', "").replace('"', "")).join(", ")}`
  );
  process.exit(1);
}

if (!appSource.includes('data-auto-translate-root="true"') || !translationSource.includes("data-auto-translate-root")) {
  console.error("Whole-app translation root check failed.");
  process.exit(1);
}

console.log("Protected route check passed.");
