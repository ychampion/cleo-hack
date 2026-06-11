import { Route, Routes } from 'react-router';
import { Shell } from './components/Shell';
import { OverviewProvider } from './lib/overview';
import { BriefView } from './views/Brief';
import { InboxView } from './views/Inbox';
import { ThemesView } from './views/Themes';
import { BetsView } from './views/Bets';
import { ActionsView } from './views/Actions';
import { AgentView } from './views/Agent';
import { DirectivesView } from './views/Directives';

export default function App() {
  return (
    <OverviewProvider>
      <Routes>
        <Route element={<Shell />}>
          <Route index element={<BriefView />} />
          <Route path="inbox" element={<InboxView />} />
          <Route path="themes" element={<ThemesView />} />
          <Route path="bets" element={<BetsView />} />
          <Route path="actions" element={<ActionsView />} />
          <Route path="agent" element={<AgentView />} />
          <Route path="directives" element={<DirectivesView />} />
          <Route path="*" element={<BriefView />} />
        </Route>
      </Routes>
    </OverviewProvider>
  );
}
