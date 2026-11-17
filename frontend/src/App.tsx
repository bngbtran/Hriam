import { Route, Routes } from "react-router-dom";
import { Layout } from "./components/Layout";
import { RequireAuth } from "./components/ui";
import { AdminLayout } from "./features/admin/AdminLayout";
import { AdminAppeals } from "./features/admin/AdminAppeals";
import { AdminAudit } from "./features/admin/AdminAudit";
import { AdminCandidates } from "./features/admin/AdminCandidates";
import { AdminContributions } from "./features/admin/AdminContributions";
import { AdminHome } from "./features/admin/AdminHome";
import { AdminModeration } from "./features/admin/AdminModeration";
import { AdminReleases } from "./features/admin/AdminReleases";
import { AdminSettings } from "./features/admin/AdminSettings";
import { AdminUsers } from "./features/admin/AdminUsers";
import { LoginPage, RegisterPage } from "./features/auth/AuthPages";
import { AppealsPage } from "./features/community/AppealsPage";
import { FeedPage } from "./features/community/FeedPage";
import { MySubmissionsPage } from "./features/community/MySubmissionsPage";
import { NewPostPage } from "./features/community/NewPostPage";
import { PostPage } from "./features/community/PostPage";
import { ContributePage } from "./features/contribute/ContributePage";
import { ConversationPage, RoomPage } from "./features/conversation/ConversationPage";
import { CulturePage } from "./features/culture/CulturePage";
import { DictionaryPage } from "./features/dictionary/DictionaryPage";
import { EntryPage } from "./features/dictionary/EntryPage";
import { HomePage } from "./features/home/HomePage";
import { AboutPage, NotFound, PrivacyPage, RulesPage } from "./features/info/InfoPages";
import { ProfilePage } from "./features/profile/ProfilePage";
import { TranslatePage } from "./features/translate/TranslatePage";

// Cấu trúc route theo docs/02 §2.2
export function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<HomePage />} />
        <Route path="translate" element={<TranslatePage />} />
        <Route path="dictionary" element={<DictionaryPage />} />
        <Route path="dictionary/:entryId" element={<EntryPage />} />
        <Route path="community" element={<FeedPage />} />
        <Route path="community/posts/:postId" element={<PostPage />} />
        <Route path="community/new" element={<RequireAuth perm="forum.post"><NewPostPage /></RequireAuth>} />
        <Route path="community/appeals" element={<RequireAuth><AppealsPage /></RequireAuth>} />
        <Route path="community/my-submissions" element={<RequireAuth><MySubmissionsPage /></RequireAuth>} />
        <Route path="contribute" element={<ContributePage />} />
        <Route path="conversation" element={<ConversationPage />} />
        <Route path="conversation/new" element={<ConversationPage />} />
        <Route path="conversation/room/:roomCode" element={<RoomPage />} />
        <Route path="culture" element={<CulturePage />} />
        <Route path="profile" element={<RequireAuth><ProfilePage /></RequireAuth>} />
        <Route path="login" element={<LoginPage />} />
        <Route path="register" element={<RegisterPage />} />
        <Route path="about" element={<AboutPage />} />
        <Route path="rules" element={<RulesPage />} />
        <Route path="privacy" element={<PrivacyPage />} />
        <Route path="admin" element={<RequireAuth><AdminLayout /></RequireAuth>}>
          <Route index element={<AdminHome />} />
          <Route path="moderation" element={<AdminModeration />} />
          <Route path="contributions" element={<AdminContributions />} />
          <Route path="lexical-candidates" element={<AdminCandidates />} />
          <Route path="dataset-releases" element={<AdminReleases />} />
          <Route path="users" element={<AdminUsers />} />
          <Route path="appeals" element={<AdminAppeals />} />
          <Route path="audit" element={<AdminAudit />} />
          <Route path="settings" element={<AdminSettings />} />
        </Route>
        <Route path="*" element={<NotFound />} />
      </Route>
    </Routes>
  );
}
