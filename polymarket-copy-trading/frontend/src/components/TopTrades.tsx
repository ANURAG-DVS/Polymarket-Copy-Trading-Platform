import { useTopTrades } from '../hooks/useTopTrades';
import { TrendingUp, DollarSign, Clock, ArrowUpRight } from 'lucide-react';

export default function TopTrades() {
    const { data: trades, isLoading, error } = useTopTrades(24, 10);

    if (isLoading) {
        return (
            <div className="bg-white rounded-lg shadow p-6">
                <h2 className="text-2xl font-bold mb-4">Top Trades (24h)</h2>
                <div className="animate-pulse space-y-4">
                    {[...Array(5)].map((_, i) => (
                        <div key={i} className="h-20 bg-gray-200 rounded"></div>
                    ))}
                </div>
            </div>
        );
    }

    if (error) {
        return (
            <div className="bg-white rounded-lg shadow p-6">
                <h2 className="text-2xl font-bold mb-4">Top Trades (24h)</h2>
                <p className="text-red-600">Error loading top trades</p>
            </div>
        );
    }

    const formatVolume = (volume: number) => {
        if (volume >= 1000000) return `$${(volume / 1000000).toFixed(2)}M`;
        if (volume >= 1000) return `$${(volume / 1000).toFixed(0)}K`;
        return `$${volume.toFixed(0)}`;
    };

    const formatPrice = (price: number) => {
        return `${(price * 100).toFixed(1)}¢`;
    };

    return (
        <div className="bg-white rounded-lg shadow">
            <div className="p-6 border-b">
                <div className="flex items-center justify-between">
                    <div className="flex items-center space-x-2">
                        <TrendingUp className="h-6 w-6 text-blue-600" />
                        <h2 className="text-2xl font-bold">Top Markets by Volume (24h)</h2>
                    </div>
                    <div className="flex items-center text-sm text-gray-500">
                        <Clock className="h-4 w-4 mr-1" />
                        <span>Live</span>
                    </div>
                </div>
            </div>

            <div className="divide-y">
                {trades?.map((trade, index) => (
                    <div
                        key={trade.market_id}
                        className="p-6 hover:bg-gray-50 transition-colors cursor-pointer"
                    >
                        <div className="flex items-start justify-between">
                            <div className="flex-1">
                                <div className="flex items-center space-x-3 mb-2">
                                    <span className="flex items-center justify-center w-8 h-8 rounded-full bg-blue-100 text-blue-600 font-bold text-sm">
                                        #{index + 1}
                                    </span>
                                    <div>
                                        <h3 className="font-semibold text-lg text-gray-900 leading-tight">
                                            {trade.market_title}
                                        </h3>
                                        <div className="flex items-center space-x-3 mt-1">
                                            <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800">
                                                {trade.category}
                                            </span>
                                            <span className="text-sm text-gray-600">
                                                Betting on: <span className="font-medium">{trade.outcome}</span>
                                            </span>
                                        </div>
                                    </div>
                                </div>

                                <div className="grid grid-cols-3 gap-4 mt-4">
                                    <div>
                                        <div className="text-xs text-gray-500 mb-1">24h Volume</div>
                                        <div className="flex items-center space-x-1">
                                            <DollarSign className="h-4 w-4 text-green-600" />
                                            <span className="text-lg font-bold text-gray-900">
                                                {formatVolume(trade.volume_24h)}
                                            </span>
                                        </div>
                                    </div>

                                    <div>
                                        <div className="text-xs text-gray-500 mb-1">Current Price</div>
                                        <div className="text-lg font-bold text-gray-900">
                                            {formatPrice(trade.current_price)}
                                        </div>
                                    </div>

                                    <div>
                                        <div className="text-xs text-gray-500 mb-1">Liquidity</div>
                                        <div className="flex items-center space-x-1">
                                            <DollarSign className="h-4 w-4 text-blue-600" />
                                            <span className="text-lg font-bold text-gray-900">
                                                {formatVolume(trade.liquidity)}
                                            </span>
                                        </div>
                                    </div>
                                </div>
                            </div>

                            <div className="ml-4">
                                <button className="flex items-center space-x-1 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors">
                                    <span>Trade</span>
                                    <ArrowUpRight className="h-4 w-4" />
                                </button>
                            </div>
                        </div>

                        <div className="mt-3 pt-3 border-t border-gray-100">
                            <div className="flex items-center justify-between text-xs text-gray-500">
                                <span>Ends: {new Date(trade.end_date).toLocaleDateString()}</span>
                                <span>Market ID: {trade.market_id.slice(0, 10)}...</span>
                            </div>
                        </div>
                    </div>
                ))}
            </div>

            {trades && trades.length === 0 && (
                <div className="p-12 text-center text-gray-500">
                    <TrendingUp className="h-12 w-12 mx-auto mb-4 opacity-50" />
                    <p>No top trades available at this time</p>
                </div>
            )}
        </div>
    );
}
