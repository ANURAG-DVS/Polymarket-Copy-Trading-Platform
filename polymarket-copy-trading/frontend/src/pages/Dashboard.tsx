import TopTrades from '../components/TopTrades';
import Leaderboard from '../components/Leaderboard';
import { BarChart3, TrendingUp, Users, DollarSign } from 'lucide-react';

export default function Dashboard() {
    // Mock data for dashboard stats
    const stats = [
        {
            title: 'Total P&L',
            value: '$12,450.50',
            change: '+24.5%',
            icon: DollarSign,
            color: 'text-green-600',
            bgColor: 'bg-green-100',
        },
        {
            title: 'Active Traders',
            value: '12',
            change: '+3',
            icon: Users,
            color: 'text-blue-600',
            bgColor: 'bg-blue-100',
        },
        {
            title: 'Win Rate',
            value: '68.5%',
            change: '+2.3%',
            icon: TrendingUp,
            color: 'text-purple-600',
            bgColor: 'bg-purple-100',
        },
        {
            title: 'Total Volume',
            value: '$145K',
            change: '+12.8%',
            icon: BarChart3,
            color: 'text-orange-600',
            bgColor: 'bg-orange-100',
        },
    ];

    return (
        <div className="min-h-screen bg-gray-50">
            <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
                {/* Header */}
                <div className="mb-8">
                    <h1 className="text-3xl font-bold text-gray-900">Dashboard</h1>
                    <p className="mt-2 text-sm text-gray-600">
                        Overview of your copy trading performance
                    </p>
                </div>

                {/* Stats Grid */}
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
                    {stats.map((stat) => (
                        <div key={stat.title} className="bg-white rounded-lg shadow p-6">
                            <div className="flex items-center justify-between">
                                <div>
                                    <p className="text-sm text-gray-600">{stat.title}</p>
                                    <p className="text-2xl font-bold text-gray-900 mt-1">
                                        {stat.value}
                                    </p>
                                    <p className="text-sm text-green-600 mt-2">{stat.change}</p>
                                </div>
                                <div className={`${stat.bgColor} p-3 rounded-lg`}>
                                    <stat.icon className={`h-6 w-6 ${stat.color}`} />
                                </div>
                            </div>
                        </div>
                    ))}
                </div>

                {/* Top Trades Section */}
                <div className="mb-8">
                    <TopTrades />
                </div>

                {/* Leaderboard Section */}
                <div>
                    <h2 className="text-2xl font-bold text-gray-900 mb-4">
                        Top Traders
                    </h2>
                    <Leaderboard />
                </div>
            </div>
        </div>
    );
}
