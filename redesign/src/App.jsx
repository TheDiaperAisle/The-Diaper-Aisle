import { useEffect } from "react";
import Header from "./components/Header";
import Tracker from "./pages/Tracker";
import Trends from "./pages/Trends";
import { useData, useRoute } from "./lib/store";
import { CATS } from "./lib/data";

const CAT_OF = { diapers: "diaper", pullups: "pullup", boosters: "booster" };

export default function App() {
  const route = useRoute();
  const data = useData();
  useEffect(() => {
    document.title = route === "trends" ? "Price trends · The Diaper Aisle" : `${CATS[CAT_OF[route]].label} prices · The Diaper Aisle`;
  }, [route]);
  return (
    <>
      <Header route={route} data={data} />
      {route === "trends" ? <Trends data={data} /> : <Tracker cat={CAT_OF[route]} data={data} />}
    </>
  );
}
