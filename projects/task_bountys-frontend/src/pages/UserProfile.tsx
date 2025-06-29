import React from 'react';
import Layout from '../components/Layout/Layout';
import { useWallet } from '../context/WalletContext';
import { useTask } from '../context/TaskContext';
import { Star } from 'lucide-react';

const UserProfile: React.FC = () => {
  const { state: walletState } = useWallet();
  const { state: taskState } = useTask();

  const wallet = walletState.account?.address;
  const createdCount = taskState.tasks.filter(t => t.creator === wallet).length;
  const claimedCount = taskState.claimedTasks.length;
  const completedCount = taskState.claimedTasks.filter(t => t.status === 'completed').length;
  const voteCount = taskState.votes?.length || 0;

  const completionRate = claimedCount > 0
    ? Math.round((completedCount / claimedCount) * 100)
    : 0;

  return (
    <Layout>
      <div className="card p-6">
        <h1 className="text-2xl font-bold text-slate-900 mb-4">👤 My Profile</h1>
        <div className="space-y-2 text-slate-700 text-sm">
          <p><strong>Wallet:</strong> <span className="font-mono">{wallet}</span></p>
          <p><strong>Tasks Created:</strong> {createdCount}</p>
          <p><strong>Tasks Claimed:</strong> {claimedCount}</p>
          <p><strong>Tasks Completed:</strong> {completedCount}</p>
          <p><strong>Completion Rate:</strong> {completionRate}%</p>
          <p><strong>DAO Votes Participated:</strong> {voteCount}</p>
          <p className="flex items-center gap-2"><Star size={14} className="text-yellow-500" /> <strong>Rating:</strong> Coming soon...</p>
        </div>
      </div>
    </Layout>
  );
};

export default UserProfile;
