class SkillReader < Formula
  desc "Rust CLI for reusable AI skill profiles"
  homepage "https://github.com/dmontil/skill-reader"
  url "https://github.com/dmontil/skill-reader/archive/refs/tags/v0.1.0.tar.gz"
  sha256 "71f8b25daf7d97cd41a66a8956b67d6cb183a607b6f433cef3ae88a0ce743d14"
  license "MIT"

  depends_on "rust" => :build

  def install
    system "cargo", "install", *std_cargo_args(path: ".")
  end

  test do
    output = shell_output("#{bin}/skill-reader profile list")
    assert_match "No profiles found", output
  end
end
