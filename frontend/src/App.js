import "@/App.css";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { TimerDisplay } from "@/components/TimerDisplay";
import { VmixDisplay } from "@/components/VmixDisplay";
import { OtaDisplay } from "@/components/OtaDisplay";
import SettingsPage from "@/components/SettingsPage";

function App() {
  return (
    <div className="App">
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<TimerDisplay />} />
          <Route path="/vmix" element={<VmixDisplay />} />
          <Route path="/ota" element={<OtaDisplay />} />
          <Route path="/settings" element={<SettingsPage />} />
        </Routes>
      </BrowserRouter>
    </div>
  );
}

export default App;
