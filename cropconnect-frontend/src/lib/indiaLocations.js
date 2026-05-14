import { getAllStates, getDistricts } from "india-state-district";
import * as indianPlaces from "indian_places";

const collator = new Intl.Collator("en-IN", { sensitivity: "base" });

const normalizeLocationName = (value = "") =>
  String(value)
    .trim()
    .toLowerCase()
    .replace(/&/g, "and")
    .replace(/\band\b/g, "")
    .replace(/[^a-z0-9]/g, "");

const uniqueSorted = (items = []) =>
  [...new Set(items.map((item) => String(item || "").trim()).filter(Boolean))]
    .sort((a, b) => collator.compare(a, b));

const placeStates = indianPlaces.getStates?.() || [];
const placeStateByName = new Map(
  placeStates.map((state) => [normalizeLocationName(state.name), state])
);

export const INDIA_STATES = getAllStates()
  .map((state) => ({
    code: state.code,
    name: state.name,
  }))
  .sort((a, b) => collator.compare(a.name, b.name));

export const findIndiaState = (stateValue = "") => {
  const normalized = normalizeLocationName(stateValue);
  return INDIA_STATES.find(
    (state) =>
      normalizeLocationName(state.name) === normalized ||
      normalizeLocationName(state.code) === normalized
  );
};

export const getDistrictOptions = (stateValue = "") => {
  const state = findIndiaState(stateValue);
  if (!state?.code) return [];
  return uniqueSorted(getDistricts(state.code));
};

export const getPlaceOptions = (stateValue = "", districtValue = "") => {
  const state = findIndiaState(stateValue);
  const district = String(districtValue || "").trim();
  if (!state?.name || !district) return [];

  const placeState = placeStateByName.get(normalizeLocationName(state.name));
  const placeDistrict = placeState
    ?.getDistricts()
    ?.find((item) => normalizeLocationName(item.name) === normalizeLocationName(district));
  const placeNames = placeDistrict?.getPlaces?.().map((item) => item.name) || [];
  const options = uniqueSorted(placeNames);

  return options.length ? options : [district];
};
