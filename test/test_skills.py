from pathlib import Path

from src.tools.builtin.skill import SkillLoader, SkillTool


def test_skill_loader():
    project_root = "./"
    loader = SkillLoader(str(project_root))
    skills = loader.scan()
    assert len(skills) == 1




def test_skill_tool():
    project_root = "./"
    skill_tool = SkillTool(project_root=Path(project_root))

if __name__ == '__main__':
    # test_skill_loader()
    test_skill_tool()
