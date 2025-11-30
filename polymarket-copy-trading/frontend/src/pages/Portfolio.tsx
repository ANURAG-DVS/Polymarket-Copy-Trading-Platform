import { useState } from 'react';
import { Wallet, TrendingUp, TrendingDown, Filter, Download } from 'lucide-react';

export default function Portfolio() {
    const [filter, setFilter] = useState('all'); // all, open, closed

    // Mock portfolio data
    const positions = [
        {
            id: 1,
            market: 'Will Bitcoin hit $100,000 by end of 2025?',
            outcome: 'Yes',
            entry_price: 0.65,
            current_price: 0.72,
            quantity: 100,
            invested: 65.00,
            current_value: 72.00,
            pnl: 7.00,
            status: 'open',
            trader: '0x1234...5678',
        },
        {
            id: 2,
            market: 'Will the Fed cut rates in Q1 2025?',
            outcome: 'Yes',
            entry_price: 0.58,
            current_price: 0.65,
            quantity: 150,
            invested: 87.00,
            current_value: 97.50,
            pnl: 10.50,
            status: 'open',
            trader: '0xabcd...ef12',
        },
        {
            id: 3,
            market: 'Will Tesla stock reach $400 in 2025?',
            outcome: 'Yes',
            entry_price: 0.62,
            current_price: 0.58,
            quantity: 80,
            invested: 49.60,
            current_value: 46.40,
            pnl: -3.20,
            status: 'open',
            trader: '0x9876...5432',
        },
        {
            id: 4,
            market: 'Will AI replace 50% of jobs by 2030?',
            outcome: 'No',
            entry_price: 0.45,
            current_price: 0.40,
            quantity: 120,
            invested: 54.00,
            current_value: 48.00,
            pnl: -6.00,
            status: 'closed',
            trader: '0xfedc...ba98',
        },
    ];

    const filteredPositions = positions.filter(p =>
        filter === 'all' ? true : p.status === filter
    );

    const totalInvested = positions.reduce((sum, p) => sum + p.invested, 0);
    const totalValue = positions.filter(p => p.status === 'open').reduce((sum, p) => sum + p.current_value, 0);
    const totalPnL = positions.reduce((sum, p) => sum + p.pnl, 0);
    const roiPercent = ((totalPnL / totalInvested) * 100).toFixed(2);

    return (
        <div className="min-h-screen bg-gray-50">
            <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
                {/* Header */}
                <div className="mb-8">
                    <h1 className="text-3xl font-bold text-gray-900">Portfolio</h1>
                    <p className="mt-2 text-sm text-gray-600">
                        View and manage all your positions
                    </p>
                </div>

                {/* Summary Cards */}
                <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
                    <div className="bg-white rounded-lg shadow p-6">
                        <div className="flex items-center justify-between">
                            <div>
                                <p className="text-sm text-gray-600">Total Invested</p>
                                <p className="text-2xl font-bold text-gray-900 mt-1">
                                    ${totalInvested.toFixed(2)}
                                </p>
                            </div>
                            <Wallet className="h-8 w-8 text-blue-600" />
                        </div>
                    </div>

                    <div className="bg-white rounded-lg shadow p-6">
                        <div className="flex items-center justify-between">
                            <div>
                                <p className="text-sm text-gray-600">Current Value</p>
                                <p className="text-2xl font-bold text-gray-900 mt-1">
                                    ${totalValue.toFixed(2)}
                                </p>
                            </div>
                            <TrendingUp className="h-8 w-8 text-green-600" />
                        </div>
                    </div>

                    <div className="bg-white rounded-lg shadow p-6">
                        <div className="flex items-center justify-between">
                            <div>
                                <p className="text-sm text-gray-600">Total P&L</p>
                                <p className={`text-2xl font-bold mt-1 ${totalPnL >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                                    {totalPnL >= 0 ? '+' : ''}${totalPnL.toFixed(2)}
                                </p>
                            </div>
                            {totalPnL >= 0 ? (
                                <TrendingUp className="h-8 w-8 text-green-600" />
                            ) : (
                                <TrendingDown className="h-8 w-8 text-red-600" />
                            )}
                        </div>
                    </div>

                    <div className="bg-white rounded-lg shadow p-6">
                        <div className="flex items-center justify-between">
                            <div>
                                <p className="text-sm text-gray-600">ROI</p>
                                <p className={`text-2xl font-bold mt-1 ${parseFloat(roiPercent) >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                                    {parseFloat(roiPercent) >= 0 ? '+' : ''}{roiPercent}%
                                </p>
                            </div>
                            <TrendingUp className="h-8 w-8 text-purple-600" />
                        </div>
                    </div>
                </div>

                {/* Filters and Actions */}
                <div className="bg-white rounded-lg shadow mb-8">
                    <div className="p-6 border-b flex items-center justify-between">
                        <div className="flex items-center space-x-4">
                            <Filter className="h-5 w-5 text-gray-400" />
                            <div className="flex space-x-2">
                                <button
                                    onClick={() => setFilter('all')}
                                    className={`px-4 py-2 rounded-lg font-medium transition-colors ${filter === 'all'
                                            ? 'bg-blue-600 text-white'
                                            : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                                        }`}
                                >
                                    All Positions
                                </button>
                                <button
                                    onClick={() => setFilter('open')}
                                    className={`px-4 py-2 rounded-lg font-medium transition-colors ${filter === 'open'
                                            ? 'bg-blue-600 text-white'
                                            : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                                        }`}
                                >
                                    Open
                                </button>
                                <button
                                    onClick={() => setFilter('closed')}
                                    className={`px-4 py-2 rounded-lg font-medium transition-colors ${filter === 'closed'
                                            ? 'bg-blue-600 text-white'
                                            : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                                        }`}
                                >
                                    Closed
                                </button>
                            </div>
                        </div>

                        <button className="flex items-center space-x-2 px-4 py-2 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 transition-colors">
                            <Download className="h-4 w-4" />
                            <span>Export</span>
                        </button>
                    </div>

                    {/* Positions Table */}
                    <div className="overflow-x-auto">
                        <table className="w-full">
                            <thead className="bg-gray-50 border-b">
                                <tr>
                                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                                        Market
                                    </th>
                                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                                        Outcome
                                    </th>
                                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                                        Entry
                                    </th>
                                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                                        Current
                                    </th>
                                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                                        Invested
                                    </th>
                                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                                        Value
                                    </th>
                                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                                        P&L
                                    </th>
                                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                                        Status
                                    </th>
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-gray-200">
                                {filteredPositions.map((position) => (
                                    <tr key={position.id} className="hover:bg-gray-50">
                                        <td className="px-6 py-4">
                                            <div>
                                                <div className="font-medium text-gray-900">
                                                    {position.market}
                                                </div>
                                                <div className="text-sm text-gray-500">
                                                    Trader: {position.trader}
                                                </div>
                                            </div>
                                        </td>
                                        <td className="px-6 py-4">
                                            <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800">
                                                {position.outcome}
                                            </span>
                                        </td>
                                        <td className="px-6 py-4 text-sm text-gray-900">
                                            {(position.entry_price * 100).toFixed(1)}¢
                                        </td>
                                        <td className="px-6 py-4 text-sm text-gray-900">
                                            {(position.current_price * 100).toFixed(1)}¢
                                        </td>
                                        <td className="px-6 py-4 text-sm text-gray-900">
                                            ${position.invested.toFixed(2)}
                                        </td>
                                        <td className="px-6 py-4 text-sm text-gray-900">
                                            ${position.current_value.toFixed(2)}
                                        </td>
                                        <td className="px-6 py-4">
                                            <span className={`text-sm font-medium ${position.pnl >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                                                {position.pnl >= 0 ? '+' : ''}${position.pnl.toFixed(2)}
                                            </span>
                                        </td>
                                        <td className="px-6 py-4">
                                            <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${position.status === 'open'
                                                    ? 'bg-green-100 text-green-800'
                                                    : 'bg-gray-100 text-gray-800'
                                                }`}>
                                                {position.status}
                                            </span>
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>

                    {filteredPositions.length === 0 && (
                        <div className="p-12 text-center text-gray-500">
                            <Wallet className="h-12 w-12 mx-auto mb-4 opacity-50" />
                            <p className="text-lg font-medium">No positions found</p>
                            <p className="text-sm mt-2">Start copying traders to build your portfolio</p>
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}
