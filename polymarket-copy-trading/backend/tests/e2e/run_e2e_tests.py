#!/usr/bin/env python3
"""
End-to-End Test Runner
Executes all E2E tests and generates comprehensive report
"""

import subprocess
import json
import time
from datetime import datetime
from pathlib import Path
import sys

class TestRunner:
    """E2E test runner with reporting"""
    
    def __init__(self):
        self.results = {
            "timestamp": datetime.now().isoformat(),
            "tests": [],
            "summary": {
                "total": 0,
                "passed": 0,
                "failed": 0,
                "skipped": 0,
                "duration": 0
            }
        }
    
    def run_tests(self):
        """Run all E2E tests"""
        
        print("🚀 Starting End-to-End Tests")
        print("="*60)
        
        start_time = time.time()
        
        # Run pytest with E2E markers
        cmd = [
            "pytest",
            "tests/e2e/",
            "-v",
            "--tb=short",
            "--json-report",
            "--json-report-file=test_results.json"
        ]
        
        print(f"\n💻 Running command: {' '.join(cmd)}\n")
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=Path(__file__).parent.parent
            )
            
            # Parse results
            self._parse_results(result)
            
        except Exception as e:
            print(f"❌ Error running tests: {e}")
            return False
        
        # Calculate duration
        self.results["summary"]["duration"] = time.time() - start_time
        
        # Generate report
        self._generate_report()
        
        return self.results["summary"]["failed"] == 0
    
    def _parse_results(self, result):
        """Parse test results"""
        
        print(result.stdout)
        
        if result.returncode == 0:
            print("\n✅ All tests passed!")
        else:
            print(f"\n❌ Some tests failed (exit code: {result.returncode})")
        
        # Try to load JSON report
        report_file = Path(__file__).parent.parent / "test_results.json"
        if report_file.exists():
            with open(report_file) as f:
                json_results = json.load(f)
                self.results["tests"] = json_results.get("tests", [])
                summary = json_results.get("summary", {})
                self.results["summary"]["total"] = summary.get("total", 0)
                self.results["summary"]["passed"] = summary.get("passed", 0)
                self.results["summary"]["failed"] = summary.get("failed", 0)
    
    def _generate_report(self):
        """Generate markdown test report"""
        
        report = []
        report.append("# End-to-End Test Report")
        report.append(f"\n**Date:** {self.results['timestamp']}")
        report.append(f"**Duration:** {self.results['summary']['duration']:.2f}s\n")
        
        # Summary
        report.append("## Summary\n")
        report.append(f"- **Total Tests:** {self.results['summary']['total']}")
        report.append(f"- **Passed:** ✅ {self.results['summary']['passed']}")
        report.append(f"- **Failed:** ❌ {self.results['summary']['failed']}")
        report.append(f"- **Skipped:** ⏭️  {self.results['summary']['skipped']}")
        
        # Pass rate
        if self.results['summary']['total'] > 0:
            pass_rate = (self.results['summary']['passed'] / 
                        self.results['summary']['total'] * 100)
            report.append(f"- **Pass Rate:** {pass_rate:.1f}%")
        
        # Test categories
        report.append("\n## Test Categories\n")
        report.append("### ✅ Complete User Journey")
        report.append("- User registration and login")
        report.append("- API key management")
        report.append("- Trader browsing")
        report.append("- Copy relationship creation")
        report.append("- Dashboard access\n")
        
        report.append("### 🔴 Failure Scenarios")
        report.append("- Insufficient funds handling")
        report.append("- API downtime resilience")
        report.append("- Invalid API keys")
        report.append("- Rate limiting\n")
        
        report.append("### 🔒 Security Audit")
        report.append("- Authentication enforcement")
        report.append("- User data isolation")
        report.append("- SQL injection prevention")
        report.append("- XSS prevention")
        report.append("- Password security\n")
        
        # Recommendations
        report.append("## Recommendations\n")
        
        if self.results['summary']['failed'] == 0:
            report.append("✅ **All tests passed!** Platform is ready for launch.\n")
        else:
            report.append("⚠️ **Some tests failed.** Review failures before launch.\n")
        
        # Next steps
        report.append("## Next Steps\n")
        report.append("1. Review any failed tests")
        report.append("2. Run load tests with Locust")
        report.append("3. Perform manual testing")
        report.append("4. Security audit review")
        report.append("5. Production deployment preparation")
        
        # Write report
        report_file = Path(__file__).parent.parent / "TEST_REPORT.md"
        with open(report_file, 'w') as f:
            f.write('\n'.join(report))
        
        print(f"\n📝 Test report generated: {report_file}")

def main():
    """Main entry point"""
    
    runner = TestRunner()
    success = runner.run_tests()
    
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
