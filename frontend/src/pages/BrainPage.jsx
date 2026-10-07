import { TopBar } from '../components/TopBar';
import BrainSection from '../components/BrainSection';

// Brain knowledge base page wrapper
export default function BrainPage() {
  return (
    <div className="min-h-screen">
      <TopBar />
      <main className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-8 sm:py-10">
        <BrainSection />
      </main>
    </div>
  );
}
