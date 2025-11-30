import React, { useState } from 'react';
import { useTraders } from '@/hooks/useTraders';
import { ArrowUpDown, Search, TrendingUp, TrendingDown } from 'lucide-react';

const Leaderboard: React.FC = () => {
    const [filters, setFilters] = useState({
        page: 1,
        limit: 10,
        sort_by: 'pnl_7d',
        sort_order: 'desc' as 'asc' | 'desc',
        search: ''
    });

    const { data, isLoading, error } = useTraders(filters);

    if (isLoading) return <div className="p-8 text-center">Loading leaderboard...</div>;
    if (error) return <div className="p-8 text-center text-red-500">Error loading leaderboard</div>;

    const traders = data?.items || [];

    return (
        <div className="bg-white shadow-md rounded-lg overflow-hidden">
            <div className="p-4 border-b border-gray-200 flex justify-between items-center bg-gray-50">
                <h2 className="text-xl font-semibold text-gray-800">Top Traders</h2>
                <div className="relative">
                    <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 h-4 w-4" />
                    <input
                        type="text"
                        placeholder="Search traders..."
                        className="pl-10 pr-4 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                        value={filters.search}
                        onChange={(e) => setFilters({ ...filters, search: e.target.value })}
                    />
                </div>
            </div>

            <div className="overflow-x-auto">
                <table className="min-w-full divide-y divide-gray-200">
                    <thead className="bg-gray-50">
                        <tr>
                            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Rank</th>
                            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Trader</th>
                            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider cursor-pointer hover:text-gray-700"
                                onClick={() => setFilters(f => ({ ...f, sort_by: 'pnl_7d', sort_order: f.sort_order === 'asc' ? 'desc' : 'asc' }))}>
                                <div className="flex items-center">
                                    P&L (7d) <ArrowUpDown className="ml-1 h-3 w-3" />
                                </div>
                            </th>
                            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Win Rate</th>
                            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Trades</th>
                            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Actions</th>
                        </tr>
                    </thead>
                    <tbody className="bg-white divide-y divide-gray-200">
                        {traders.map((trader: any, index: number) => (
                            <tr key={trader.id} className="hover:bg-gray-50">
                                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                                    #{((filters.page - 1) * filters.limit) + index + 1}
                                </td>
                                <td className="px-6 py-4 whitespace-nowrap">
                                    <div className="flex items-center">
                                        <div className="h-8 w-8 rounded-full bg-blue-100 flex items-center justify-center text-blue-600 font-bold mr-3">
                                            {trader.address.substring(0, 2)}
                                        </div>
                                        <div>
                                            <div className="text-sm font-medium text-gray-900">{trader.address.substring(0, 6)}...{trader.address.substring(38)}</div>
                                            <div className="text-xs text-gray-500">Vol: ${trader.volume?.toLocaleString()}</div>
                                        </div>
                                    </div>
                                </td>
                                <td className="px-6 py-4 whitespace-nowrap">
                                    <div className={`text-sm font-semibold flex items-center ${trader.pnl >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                                        {trader.pnl >= 0 ? <TrendingUp className="h-4 w-4 mr-1" /> : <TrendingDown className="h-4 w-4 mr-1" />}
                                        ${Math.abs(trader.pnl).toLocaleString()}
                                    </div>
                                </td>
                                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-700">
                                    {(trader.win_rate * 100).toFixed(1)}%
                                </td>
                                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-700">
                                    {trader.total_trades}
                                </td>
                                <td className="px-6 py-4 whitespace-nowrap text-sm font-medium">
                                    <button className="text-blue-600 hover:text-blue-900 bg-blue-50 px-3 py-1 rounded-md transition-colors">
                                        Copy
                                    </button>
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>

            {/* Pagination controls could go here */}
        </div>
    );
};

export default Leaderboard;
